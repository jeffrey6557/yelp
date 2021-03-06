import time

from etl import ETLUtils
from evaluation import precision_in_top_n
from evaluation.mean_absolute_error import MeanAbsoluteError
from evaluation.root_mean_square_error import RootMeanSquareError
from recommenders.adjusted_weighted_sum_recommender import \
    AdjustedWeightedSumRecommender
from recommenders.average_recommender import AverageRecommender
from recommenders.multicriteria.delta_cf_recommender import DeltaCFRecommender
from recommenders.multicriteria.delta_recommender import DeltaRecommender
from recommenders.multicriteria.overall_cf_recommender import \
    OverallCFRecommender
from recommenders.multicriteria.overall_recommender import OverallRecommender
from recommenders.similarity.average_similarity_matrix_builder import \
    AverageSimilarityMatrixBuilder
from recommenders.similarity.multi_similarity_matrix_builder import \
    MultiSimilarityMatrixBuilder
from recommenders.similarity.single_similarity_matrix_builder import \
    SingleSimilarityMatrixBuilder
from recommenders.weighted_sum_recommender import WeightedSumRecommender
from tripadvisor.fourcity import extractor
from tripadvisor.fourcity import movielens_extractor
from recommenders.dummy_recommender import DummyRecommender


__author__ = 'fpena'


def predict_rating_list(predictor, reviews):
    """
    For each one of the reviews this method predicts the rating for the
    user and item contained in the review and also returns the error
    between the predicted rating and the actual rating the user gave to the
    item

    :param predictor: the object used to predict the rating that will be given
     by a the user to the item contained in each review
    :param reviews: a list of reviews (the test data)
    :return: a tuple with a list of the predicted ratings and the list of
    errors for those predictions
    """
    predicted_ratings = []
    errors = []
    num_unknown_ratings = 0.

    for review in reviews:

        user_id = review['user_id']
        item_id = review['offering_id']
        predicted_rating = predictor.predict_rating(user_id, item_id)
        actual_rating = review['overall_rating']

        # print(user_id, item_id, predicted_rating)

        error = None

        if predicted_rating is not None:
            error = abs(predicted_rating - actual_rating)
        else:
            num_unknown_ratings += 1

        predicted_ratings.append(predicted_rating)
        errors.append(error)

    return predicted_ratings, errors, num_unknown_ratings


def perform_cross_validation(reviews, recommender, num_folds):

    start_time = time.time()
    split = 1 - (1/float(num_folds))
    total_mean_absolute_error = 0.
    total_mean_square_error = 0.
    total_coverage = 0.
    num_cycles = 0

    for i in xrange(0, num_folds):
        print('Num cycles:', i)
        start = float(i) / num_folds
        train, test = ETLUtils.split_train_test(reviews, split=split, shuffle_data=False, start=start)
        recommender.load(train)
        _, errors, num_unknown_ratings = predict_rating_list(recommender, test)
        mean_absolute_error = MeanAbsoluteError.compute_list(errors)
        root_mean_square_error = RootMeanSquareError.compute_list(errors)
        num_samples = len(test)
        coverage = float((num_samples - num_unknown_ratings) / num_samples)
        # print('Total length:', len(test))
        # print('Unknown ratings:', num_unknown_ratings)
        # print('Coverage:', coverage)

        if mean_absolute_error is not None:
            total_mean_absolute_error += mean_absolute_error
            total_mean_square_error += root_mean_square_error
            total_coverage += coverage
            num_cycles += 1
        else:
            print('Mean absolute error is None!!!')


    final_mean_absolute_error = total_mean_absolute_error / num_cycles
    final_root_squared_error = total_mean_square_error / num_cycles
    final_coverage = total_coverage / num_cycles
    execution_time = time.time() - start_time

    print('Final mean absolute error: %f' % final_mean_absolute_error)
    print('Final root mean square error: %f' % final_root_squared_error)
    print('Final coverage: %f' % final_coverage)
    print("--- %s seconds ---" % execution_time)

    result = {
        'MAE': final_mean_absolute_error,
        'RMSE': final_root_squared_error,
        'Coverage': final_coverage,
        'Execution time': execution_time
    }

    return result


def evaluate_recommender_similarity_metrics(reviews, recommender):

    headers = [
        'Algorithm',
        'Multi-cluster',
        'Similarity algorithm',
        'Similarity metric',
        'Num neighbors',
        'Dataset',
        'MAE',
        'RMSE',
        'Top N',
        'Coverage',
        'Execution time',
        'Cross validation',
        'Machine'
    ]
    similarity_metrics = ['euclidean']  # , 'cosine', 'chebyshev', 'manhattan', 'pearson']
    similarity_algorithms = [
        SingleSimilarityMatrixBuilder('euclidean'),
        # AverageSimilarityMatrixBuilder('euclidean'),
        # MultiSimilarityMatrixBuilder('euclidean'),
    ]
    ranges = [
        # [(-1.001, -0.999), (0.999, 1.001)],
        # [(-1.01, -0.99), (0.99, 1.01)],
        # [(-1.05, -0.95), (0.95, 1.05)],
        # [(-1.1, -0.9), (0.9, 1.1)],
        # [(-1.2, -0.8), (0.8, 1.2)],
        # [(-1.3, -0.7), (0.7, 1.3)],
        # [(-1.5, -0.5), (0.5, 1.5)],
        # [(-1.7, -0.3), (0.3, 1.7)],
        # [(-1.9, -0.1), (0.1, 1.9)],
        None
    ]
    num_neighbors_list = [None, 1]  # , 1, 3, 5, 10, 20, 30, 40]
    num_folds = 5
    results = []

    for similarity_algorithm in similarity_algorithms:

        for num_neighbors in num_neighbors_list:

            for similarity_metric in similarity_metrics:

                for cluster_range in ranges:

                    recommender._similarity_matrix_builder = similarity_algorithm
                    recommender._similarity_matrix_builder._similarity_metric = similarity_metric
                    recommender._significant_criteria_ranges = cluster_range
                    recommender._num_neighbors = num_neighbors

                    print(
                        recommender.name, recommender._significant_criteria_ranges,
                        recommender._similarity_matrix_builder._name,
                        recommender._similarity_matrix_builder._similarity_metric,
                        recommender._num_neighbors
                    )

                    # result = perform_cross_validation(reviews, recommender, num_folds)
                    result = precision_in_top_n.calculate_top_n_precision(reviews, recommender, 5, 4.0, 5)

                    # result['Top N'] = recommender.top_n_result
                    result['Algorithm'] = recommender.name
                    result['Multi-cluster'] = recommender._significant_criteria_ranges
                    result['Similarity algorithm'] = recommender._similarity_matrix_builder._name
                    result['Similarity metric'] = recommender._similarity_matrix_builder._similarity_metric
                    result['Cross validation'] = 'Folds=' + str(num_folds) + ', Iterations = ' + str(num_folds)
                    result['Num neighbors'] = recommender._num_neighbors
                    result['Dataset'] = 'Four City'
                    result['Machine'] = 'Mac'
                    results.append(result)

    file_name = '/Users/fpena/tmp/rs-test/test-ml100k-03-knn-delete' + recommender.name + '.csv'
    ETLUtils.save_csv_file(file_name, results, headers)


def evaluate_recommenders(reviews, recommender_list):

    for recommender in recommender_list:
        evaluate_recommender_similarity_metrics(reviews, recommender)




start_time = time.time()
# main()
file_path = '/Users/fpena/tmp/filtered_reviews_multi.json'
# reviews = extractor.load_json_file(file_path)
# reviews = extractor.pre_process_reviews()
reviews = movielens_extractor.get_ml_100K_dataset()
# ETLUtils.save_json_file(file_path, reviews)
# print(reviews[0])
# print(reviews[1])
# print(reviews[2])
# print(reviews[10])
# print(reviews[100])
#
# for review in reviews:
#     print(review)


my_recommender_list = [
    # SingleCF(),
    AdjustedWeightedSumRecommender(SingleSimilarityMatrixBuilder('euclidean')),
    # AdjustedWeightedSumRecommender(MultiSimilarityMatrixBuilder('chebyshev')),
    # WeightedSumRecommender(SingleSimilarityMatrixBuilder('euclidean')),
    # WeightedSumRecommender(MultiSimilarityMatrixBuilder('cosine')),
    # DeltaRecommender(),
    # DeltaCFRecommender(),
    # OverallRecommender(),
    # OverallCFRecommender(),
    # AverageRecommender(),
    # DummyRecommender(4.0)
]


# my_reviews = extractor.load_json_file('/Users/fpena/tmp/filtered_reviews.json')
evaluate_recommenders(reviews, my_recommender_list)
# recommender = SingleCF('pearson')
# evaluate_recommender_similarity_metrics(recommender)
# recommender = OverallCFRecommender('euclidean')
# evaluate_recommender_similarity_metrics(recommender)
# perform_clu_cf_euc_top_n_validation()
# perform_clu_overall_cross_validation()
# perform_clu_overall_whole_dataset_evaluation()
# precision_in_top_n.calculate_top_n_precision(reviews, my_recommender_list[0], 5, 4.0, 5)
end_time = time.time() - start_time
print("--- %s seconds ---" % end_time)

# numerator = 4.5 * 4 + 3 * 2
# denominator = ((4.5**2)+(3**2)**0.5) * ((4**2) + (2**2) ** 0.5)
# result = numerator / denominator
# print('Result:', result)
#
# ratings1 = [4.5, 3]
# ratings2 = [4, 2]
#
# print('Cosine:', 1 - spatial.distance.cosine(ratings1, ratings2))
