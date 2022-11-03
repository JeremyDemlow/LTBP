# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/00a_Data_Creation_Script.ipynb.

# %% auto 0
__all__ = ['data_creation']

# %% ../../nbs/00a_Data_Creation_Script.ipynb 2
from fastcore.script import Param, call_parse

from data_system_utilities.azure.storage import FileHandling

from LTBP.data.utils import (
    query_feature_sets_to_adls_parquet_sf_fs, snowflake_query,
    get_yaml_dicts, pull_features_from_snowflake
)

import LTBP.files as files
import os
import logging

# %% ../../nbs/00a_Data_Creation_Script.ipynb 7
@call_parse
def data_creation(
    yaml_file_list: Param(help="YAML files to read", type=list, default=['features.yaml', 'udf_inputs.yaml', 'etl.yaml']),  # noqa:
    train_or_inference: Param(help="Upper case training or inference", type=str, default='TRAINING'),  # noqa
    experiment_name: Param(help="Experiment name to run case sensetive", type=str, default='BASELINE'),  # noqa:
    experiment: Param(help="Boolen if it's a experiment or a run to run for a commit hash", type=bool, default=True)  # noqa:
    ):  # noqa:
    """Creates a feature set for a experiment data set or a production level run feature set"""
    logging.info(f"This is a {'experiment run' if experiment else 'production run'}")
    logging.info('Loading Yaml Files..')
    features, udf_inputs, etl = get_yaml_dicts(yaml_file_list)
    logging.info('Generating Feature Set Query')
    query = pull_features_from_snowflake(feature_dict=features,
                                         udf_inputs=udf_inputs[train_or_inference.upper()],
                                         filepath_to_grain_list_query=os.path.join(files.__path__[0], etl['query_file_path']),
                                         experiment_name=experiment_name)
    data_lake_path = os.path.join((os.path.join(etl['data_lake_path'], 'experiments', experiment_name)
                                   if experiment
                                   else os.path.join(etl['data_lake_path'],
                                                     os.environ.get('CI_COMMIT_SHA', 'LocalRunTest'))), train_or_inference.lower()+'_data/')
    logging.info(f'Checking {data_lake_path} to either skip creation for experiment or create a production dataset')
    fh = FileHandling(os.environ['DATALAKE_CONN_STR_SECRET'])
    ald_files = fh.ls_blob(path=data_lake_path, container_name=etl['azure_container'])
    sf = snowflake_query()
    if ald_files == []:
        query_feature_sets_to_adls_parquet_sf_fs(
            sf_connection=sf,
            sf_query=query,
            azure_account=etl["azure_account"],
            azure_container=etl["azure_container"],
            data_lake_path=data_lake_path,  # TODO: Think about experiments versus
            partition_by=None,
            data_lake_sas_token=os.environ["DATALAKE_SAS_TOKEN_SECRET"],
        )
    else:
        logging.warning(f'{data_lake_path} already exists this should be do experimentation runs')
