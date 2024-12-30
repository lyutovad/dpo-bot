from schemes import scheme_grading_exam, scheme_mba_ved, scheme_graduate, scheme_mba_business_strategy, scheme_two_diploma, scheme_resources, scheme_grading_test, scheme_grading_essay

collections_list = [
    {
        'name': 'МВА-Современные технологии управления ВЭД',
        'metadata_list': scheme_mba_ved.metadata_list,
        'attribute_info': scheme_mba_ved.attribute_info,
        'file_paths': scheme_mba_ved.file_paths
    },
    {
        'name': 'Специалитет/магистратура + МВА',
        'metadata_list': scheme_graduate.metadata_list,
        'attribute_info': scheme_graduate.attribute_info,
        'file_paths': scheme_graduate.file_paths
    },

    {
        'name': 'МВА-Стратегическое управление эффективностью бизнеса',
        'metadata_list': scheme_mba_business_strategy.metadata_list,
        'attribute_info': scheme_mba_business_strategy.attribute_info,
        'file_paths': scheme_mba_business_strategy.file_paths
    },

    {
        'name': 'Программа двух дипломов (магистратура + МВА) Бизнес-администрирование',
        'metadata_list': scheme_two_diploma.metadata_list,
        'attribute_info': scheme_two_diploma.attribute_info,
        'file_paths': scheme_two_diploma.file_paths
    },

    {
        'name': 'Электронные библиотеки и ресурсы',
        'metadata_list': scheme_resources.metadata_list,
        'attribute_info': scheme_resources.attribute_info,
        'file_paths': scheme_resources.file_paths
    },

    {
        'name': 'Критерии оценивания слушателя на экзамене по дисциплинам',
        'metadata_list': scheme_grading_exam.metadata_list,
        'attribute_info': scheme_grading_exam.attribute_info,
        'file_paths': scheme_grading_exam.file_paths
    },

    {
        'name': 'Критерии оценивания слушателя на зачете по дисциплинам',
        'metadata_list': scheme_grading_test.metadata_list,
        'attribute_info': scheme_grading_test.attribute_info,
        'file_paths': scheme_grading_test.file_paths
    },

    {
        'name': 'Критерии оценивания эссе',
        'metadata_list': scheme_grading_essay.metadata_list,
        'attribute_info': scheme_grading_essay.attribute_info,
        'file_paths': scheme_grading_essay.file_paths
    },
]