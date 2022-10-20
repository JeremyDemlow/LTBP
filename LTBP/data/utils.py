# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/00_Data_Utils.ipynb.

# %% auto 0
__all__ = ['get_yaml_dicts', 'generate_data_lake_query', 'read_sfQueries_txt_sql_file', 'return_sf_type', 'snowflake_query',
           'query_feature_sets_to_adls_parquet_sf_fs']

# %% ../../nbs/00_Data_Utils.ipynb 3
from data_system_utilities.snowflake.query import Snowflake
from data_system_utilities.snowflake.copyinto import sf_to_adls_url_query_generator
from data_system_utilities.file_parsers import yaml

from fastcore.xtras import is_listy 
from .. import files

import os
import logging
import sys

# %% ../../nbs/00_Data_Utils.ipynb 4
def get_yaml_dicts(yaml_file_names: list):
    """
    Give a list of files to this function from the /files
    in a library and it will read/Parse yaml files and
    return a list of dictionaries to unpack

    How to use:
    yaml_file_list = ['dataset.yaml', 'etl.yaml', 'experiment.yaml']
    data, etl, exp = get_yaml_dicts(yaml_file_list)

    Args:
    * yaml_file_names (list):

    Returns:
    *  list : list of dictionaries
    """
    yaml_file_names = yaml_file_names if is_listy(yaml_file_names) else list(yaml_file_names)
    yaml_dicts = []
    for yf in yaml_file_names:
        yaml_dict = yaml.yaml_reader(os.path.join(files.__path__[0], 'yaml_files', yf))
        yaml_dicts.append(yaml_dict)
    return yaml_dicts

# %% ../../nbs/00_Data_Utils.ipynb 6
def generate_data_lake_query(
    stage_name, stage_path, columns, header=True, extra_statement=None
):
    """
    Given the columns names are provided this query will query out parquet data
    from azure datalake all in varchar this is the basic approach.

    Args:
        stage_name (str): Snowflake stage name
        stage_path (str): Snowflake stage path
        columns (list): list/dict of column names
        extra_statement (str, optional): Extra snowflake command. Defaults to None.

    Returns:
        str: Query produced through this function
    """
    query = f"""
    select
    FEATURES_HERE
    from @{os.path.join(stage_name, stage_path)}
    {extra_statement}
    """
    if header is True:
        for ind, feature in enumerate(columns):
            if ind == 0:
                query = query.replace(
                    "FEATURES_HERE",
                    f'$1:"{feature}"::varchar as {feature}\nFEATURES_HERE',
                )
            else:
                query = query.replace(
                    "FEATURES_HERE",
                    f', $1:"{feature}"::varchar as {feature}\nFEATURES_HERE',
                )
    else:
        for ind, feature in enumerate(columns):
            if ind == 0:
                query = query.replace(
                    "FEATURES_HERE",
                    f'$1:"_COL_{ind}"::varchar as {feature}\nFEATURES_HERE',
                )
            else:
                query = query.replace(
                    "FEATURES_HERE",
                    f', $1:"_COL_{ind}"::varchar as {feature}\nFEATURES_HERE',
                )
    query = query.replace("FEATURES_HERE", "")
    return query

# %% ../../nbs/00_Data_Utils.ipynb 9
def read_sfQueries_txt_sql_file(file_name):
    """Simple utilty to read query files"""
    with open(os.path.join(files.__path__[0], 'sql_files', file_name)) as f:
        read_data = ''.join(f.readlines())
        f.close()
    return read_data

# %% ../../nbs/00_Data_Utils.ipynb 10
def return_sf_type(dtype: str, varchar: bool):
    """
    simple function to convert dytpes to snowflake dtypes this
    will be come a very useful thing to have as this will dtype
    Args:
    * dtype (str): dtype from a df in sting form
    * varchar (bool): to default all variables to VARCHAR
    this happens due to bad vendor data and can't be resloved
    with out reading in the whole data set with low_memory=False

    Returns:
    * str: snowflake dtype
    """
    if varchar is True:
        dtype = 'VARCHAR'
    elif 'int' in dtype.lower():
        dtype = 'NUMBER'
    elif 'float' in dtype.lower():
        dtype = 'FLOAT'
    elif 'object' in dtype.lower():
        dtype = 'VARCHAR'
    elif 'bool' in dtype.lower():
        dtype = 'VARCHAR'  # TODO: Limitation found before change once resloved by sf
    elif 'date' in dtype.lower():
        dtype = 'DATETIME'  # TODO: Might break with certain datetimes most generic
    else:
        logging.error('odd dtype not seen needs to be resloved...')
        sys.exit()
    return dtype

# %% ../../nbs/00_Data_Utils.ipynb 11
def snowflake_query(sfAccount: str = os.environ.get('sfAccount', None),
                    sfUser: str = os.environ.get('sfUser', None),
                    sfPswd: str = os.environ.get('sfPswd', None),
                    sfWarehouse: str = os.environ.get('sfWarehouse', None),
                    sfDatabase: str = os.environ.get('sfDatabase', None),
                    sfSchema: str = os.environ.get('sfSchema', None),
                    sfRole: str = os.environ.get('sfRole', None)):
    """Easy Connection To SnowFlake When Environs are set"""
    sf = Snowflake(sfAccount, sfUser, sfPswd, sfWarehouse,
                       sfDatabase, sfSchema, sfRole)
    return sf

# %% ../../nbs/00_Data_Utils.ipynb 12
def query_feature_sets_to_adls_parquet_sf_fs(
    sf_connection,
    sf_query:str,
    azure_account: str,
    azure_container: str,
    data_lake_path: str,
    query_file_path: str,
    data_lake_sas_token: str, # os.environ["DATALAKE_SAS_TOKEN_SECRET"]
    partition_by: str = None,
    max_file_size: str = "3200000",
    header: str = "True",
    over_write: str = "True",
):
    # Creating Query to create ADLS Stage for Snowflake
    url = f"azure://{azure_account}.blob.core.windows.net/{azure_container}/{data_lake_path}"
    sf_to_adls_query = sf_to_adls_url_query_generator(
        azure_path=url,
        azure_sas_token=data_lake_sas_token,
        sf_query=sf_query,
        max_file_size=max_file_size,
        file_type="parquet",
        partition_by=partition_by,
        header=header,
        overwrite=over_write,
    )
    # Execute
    _ = sf_connection.run_sql_str(sf_to_adls_query)
    logging.info(f"data has been delivered from sf to adls")
