# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/02a_Data_Creation.ipynb.

# %% auto 0
__all__ = ['data_creation']

# %% ../../nbs/02a_Data_Creation.ipynb 2
from fastcore.script import Param, call_parse

from data_system_utilities.snowflake.query import Snowflake
from data_system_utilities.azure.storage import FileHandling
from data_system_utilities.snowflake.copyinto import sf_to_adls_url_query_generator

from machine_learning_utilities.dataset_creation.snowflake import pull_features_from_snowflake

from ..data.utils import query_feature_sets_to_adls_parquet_sf_fs, snowflake_query, get_yaml_dicts
from .. import files

import os
import logging
import pandas as pd
import logging
import os

# %% ../../nbs/02a_Data_Creation.ipynb 6
@call_parse
def data_creation(train_or_inference: Param(help="YAML section to read", type=str, default='TRAINING'), # noqa:
                  experiment: Param(help="YAML section to read", type=str, default='False')):  # noqa:
    """Creates a feature set for a experiment data set or a production level run feature set"""
    experiment = True if experiment == 'True' else False
    logging.info(f"This is a {'experiment run' if experiment else 'production run'}")
    logging.info('Loading Yaml Files..')
    features, udf_inputs, etl = get_yaml_dicts(['features.yaml', 'udf_inputs.yaml', 'etl.yaml'])
    logging.info('Generating Feature Set Query')
    query = pull_features_from_snowflake(feature_dict=features,
                                         udf_inputs=udf_inputs[train_or_inference.upper()],
                                         filepath_to_grain_list_query='./LTBP/files/sql_files/')
    data_lake_path = (os.path.join(etl['data_lake_path'], 'experiments', etl['exp_name'])
                      if experiment 
                      else os.path.join(etl['data_lake_path'], 
                                        os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')))
    logging.info(f'Checking {data_lake_path} to either skip creation for experiment or create a production dataset')
    fh = FileHandling(os.environ['DATALAKE_CONN_STR_SECRET'])
    ald_files = fh.ls_blob(path=data_lake_path, container_name=etl['azure_container'])
    sf = snowflake_query()
    if ald_files == []:
        query_feature_sets_to_adls_parquet_sf_fs(
            sf_connection=sf,
            sf_query=query,
            query_file_path=os.path.join(files.__path__[0], etl['query_file_path']),
            azure_account=etl["azure_account"],
            azure_container=etl["azure_container"],
            data_lake_path=data_lake_path, # TODO: Think about experiments versus 
            partition_by=None,
            data_lake_sas_token=os.environ["DATALAKE_SAS_TOKEN_SECRET"],
        )
    else:
        logging.warning(f'{data_lake_path} already exists this should be do experimentation runs')
