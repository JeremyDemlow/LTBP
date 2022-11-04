# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/02b_Inference_Script.ipynb.

# %% auto 0
__all__ = ['model_inference']

# %% ../../nbs/02b_Inference_Script.ipynb 3
from fastcore.script import Param, call_parse

from ..modeling.utils import create_stage_and_query_stage_sf
from ..data.utils import snowflake_query, get_yaml_dicts
from ..inference.utils import pull_sklearn_object_from_adls

from data_system_utilities.snowflake.copyinto import adls_url_to_sf_query_generator
from data_system_utilities.snowflake.utils import create_table_query_from_df
from data_system_utilities.azure.storage import FileHandling

import os
import datetime
import logging

# %% ../../nbs/02b_Inference_Script.ipynb 6
@call_parse
def model_inference(
    yaml_file_list: Param(help="YAML files to read", type=list,  # noqa:
                      default=['features.yaml', 'udf_inputs.yaml', 'etl.yaml', 'models.yaml']),  # noqa:
    experiment_name: Param(help="tell function what experiment is being ran", type=str, default='BASELINE'),  # noqa:
    experiment: Param(help="add experiment state it is not an experiment", type=bool, default=True),  # noqa:
    sfSchema: Param(help="dev queries dev schema anything else will query project schema", type=str, default='dev')  # noqa:
    ):  # noqa:

    features, udf_inputs, etl_dict, models_dict = get_yaml_dicts(yaml_file_list)
    sf = snowflake_query(sfSchema=sfSchema)
    adls_paths = []
    model_names = []
    experiment_names = []
    experiments = []
    if sfSchema.lower() != 'dev':
        prod_model = sf.run_sql_str(f'''SELECT *
        FROM MACHINELEARNINGOUTPUTS.{sfSchema}.{models_dict['tracking_table']}
        WHERE PRODUCTION_MODEL
        ''')
        sf.run_sql_str(f"DROP TABLE IF EXISTS MACHINELEARNINGOUTPUTS.{sfSchema}.{models_dict['inference_sf_table_name']}")
        for i, v in prod_model.iterrows():
            adls_path = os.path.join(
                (os.path.join(etl_dict['data_lake_path'], 'experiments', v['EXPERIMENT_NAME'])
                 if v['EXPERIMENT']
                 else os.path.join(
                    etl_dict['data_lake_path'], v['COMMITID'], v['EXPERIMENT_NAME'])))
            adls_paths.append(adls_path)
            model_name = (models_dict[v['EXPERIMENT_NAME']]['model_trainer']
                          + v['COMMITID']
                          + v['EXPERIMENT_NAME']+'.pkl'
                          )
            model_names.append(model_name)
            experiment_names.append(v['EXPERIMENT_NAME'])
            experiments.append(v['EXPERIMENT'])
    else:
        adls_path = os.path.join(
            (os.path.join(etl_dict['data_lake_path'], 'experiments', experiment_name)
             if experiment
             else os.path.join(
                etl_dict['data_lake_path'], os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS'))))
        adls_paths.append(adls_path)
        model_name = (models_dict[experiment_name]['model_trainer']
                      + os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')
                      + experiment_name+'.pkl'
                      )
        model_names.append(model_name)
        experiment_names.append(experiment_name)
        experiments.append(experiment)
    """
    This came about while thinking about having more than one production model
    making a functional call to this is probably better than this long code
    """
    for adls_path, model_name, exp_name in zip(adls_paths, model_names, experiment_names):
        df_infer = create_stage_and_query_stage_sf(
            sf=sf,
            features=features,
            etl=etl_dict,
            udf_inputs=udf_inputs,
            train_or_inference='INFERENCE',
            experiment_name=exp_name,
            experiment=experiment,
            indentification=models_dict['identification'],
            extra_statement='LIMIT 1000'  # Can add limit when experimenting 'LIMIT 1000'
        )
        model = pull_sklearn_object_from_adls(
            adls_path=os.path.join(adls_path,
                                   models_dict['modeling_adls_path'],
                                   models_dict[exp_name]['model_trainer']
                                   ) + '/',
            file_name=model_name,
            drop_local_path='./models/',
            container_name=etl_dict['azure_container'],
            connection_str=os.environ[models_dict['connection_str']]
        )
        sf_df = df_infer[models_dict['identification']].copy()
        # Change Here Name change for a regression and to predict or multi-labled needs some work
        sf_df['PROBABILITY'] = model.predict_proba(df_infer)[:, 1]
        date_created = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        sf_df['CI_COMMIT_SHA'] = os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')
        sf_df['DATE_CREATED'] = datetime.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
        sf_df['EXPERIMENT'] = exp_name
        file_name = f"predictions_{os.environ.get('CI_COMMIT_SHA','LocalRunNBS')+exp_name}.csv"
        # Saving as a .csv for simple reading from adls download using dask would be best here
        sf_df.to_csv(file_name, index=False)
        logging.info(f'preview predictions being added:\n{sf_df.head(3)}')
        logging.info(f'preview predictions values addes:\n{sf_df.iloc[0].values}')
        logging.info(f'preview predictions being added columns:\n{sf_df.columns}')
        az = FileHandling(os.environ[models_dict['connection_str']])
        az.upload_file(
            azure_file_path=os.path.join(adls_path,
                                         models_dict['predictions_adls_path'],
                                         models_dict[exp_name]['model_trainer']),
            local_file_path=file_name,
            container_name=etl_dict['azure_container'],
            overwrite=True,
        )
        os.unlink(file_name)
        stage_url = f"azure://{etl_dict['azure_account']}.blob.core.windows.net/{etl_dict['azure_container']}/"
        preds_file_path = os.path.join(adls_path,
                                       models_dict['predictions_adls_path'],
                                       models_dict[exp_name]['model_trainer'],
                                       file_name)

        sf = snowflake_query(sfSchema=sfSchema)
        if models_dict['inference_sf_table_name'].upper() not in sf.run_sql_str("show tables;").name.tolist():
            sf.run_sql_str(create_table_query_from_df(sf_df, table_name_sf=models_dict['inference_sf_table_name'], varchar=False))
        logging.info("Pushing Forecasted Season from ADLS to Snowflake")
        adls_query = adls_url_to_sf_query_generator(
            azure_path=os.path.join(stage_url, preds_file_path),
            azure_sas_token=os.environ[models_dict['sas_token']],
            table_name=models_dict['inference_sf_table_name'],
            database=sf.connection_inputs['database'],
            schema=sf.connection_inputs['schema'],
            skip_header='1',
            file_type='csv',
            pattern='.*.csv')
        sf.run_sql_str(adls_query)

        exp_table = sf.run_sql_str(f"""
        SELECT *
        FROM {models_dict['inference_sf_table_name']}
        WHERE DATE_CREATED = '{date_created}'
        AND EXPERIMENT = '{exp_name}'
        LIMIT 3
        """)
        logging.info(f'preview of queried table being added:\n{exp_table.head(3)}')
        logging.info(f'preview predictions values addes:\n{exp_table.iloc[0].values}')
