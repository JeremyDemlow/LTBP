# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/01a_Model_Utilities.ipynb.

# %% auto 0
__all__ = ['return_dict_type', 'create_sklearn_preprocess_baseline_dict', 'return_list_of_vars', 'prepare_training_set',
           'preprocess_data', 'save_sklearn_object_to_data_lake', 'create_stage_and_query_stage_sf']

# %% ../../nbs/01a_Model_Utilities.ipynb 3
from data_system_utilities.azure.storage import FileHandling
from data_system_utilities.snowflake.utils import make_stage_query_generator

from machine_learning_utilities import preprocessing

from ..data.utils import snowflake_query, get_yaml_dicts, generate_data_lake_query

from sklearn.model_selection import train_test_split

from rfpimp import *

import os
import logging
import pickle
import pandas as pd

# %% ../../nbs/01a_Model_Utilities.ipynb 4
def return_dict_type(
    pre_process_type: dict  # {k:v} dictionary of columns name and tranformation type
):
    """
    Simplify the standard process for sklearn preprocessing pipelines
    """
    for k, v in pre_process_type.items():
        if v == "OrdinalEncoder":
            pre_process_dict = {
                f"{k}": {
                    "transformation": {
                        "name": "OrdinalEncoder",
                        "args": {
                            "handle_unknown": "use_encoded_value",
                            "unknown_value": -1,
                        },
                    },
                    "variable_type": "cat",
                }
            }
        if v == "OneHotEncoder":
            pre_process_dict = {
                f"{k}": {
                    "transformation": {
                        "name": "OneHotEncoder",
                        "args": {"handle_unknown": "ignore", "sparse": False},
                    },
                    "variable_type": "cat",
                }
            }
        if v == "StandardScaler":
            pre_process_dict = {
                f"{k}": {
                    "transformation": {"name": "StandardScaler", "args": {}},
                    "variable_type": "cont",
                }
            }
        if v == "RobustScaler":
            pre_process_dict = {
                f"{k}": {
                    "transformation": {"name": "RobustScaler", "args": {}},
                    "variable_type": "cont",
                }
            }
    return pre_process_dict


# %% ../../nbs/01a_Model_Utilities.ipynb 7
def create_sklearn_preprocess_baseline_dict(
    cat_vars: list,  # list of categorical variables with sklearn transformer
    cont_vars: list,  # list of continous variables with sklearn transformer
):
    """wrapper around ``return_dict_type`` to go through cat and cont vars
    """
    final_dict = {}
    if cat_vars is None:
        cat_vars = []
    if cont_vars is None:
        cont_vars = []
    for item in cat_vars + cont_vars:
        final_dict.update(return_dict_type(item))
    return final_dict


# %% ../../nbs/01a_Model_Utilities.ipynb 10
def return_list_of_vars(variables):
    """_summary_

    Args:
        variables (_type_): _description_

    Returns:
        _type_: _description_
    """
    if variables is None:
        return None
    vars_list = []
    for item in variables:
        for k in item.keys():
            vars_list.append(k)
    return vars_list


# %% ../../nbs/01a_Model_Utilities.ipynb 13
def prepare_training_set(df: pd.DataFrame,
                         y_var: list,
                         y_scaler_type:object,
                         sklearn_pipe:object,
                         etl_dict: dict,
                         models_dict: dict,
                         adls_path: str,
                         experiment_name: str,
                         connection_str: str,
                         identifiers: list = ['ECID'],
                         test_set: bool = True,
                         validation_split: float = .20,
                         test_split: float = .15,
                         seed: int = 1320,
                         as_type=int):
    """TODO: Working on Multi-Col Labels split and preprocess data set for model training purposes"""
    scaler = y_scaler_type
    # Sklearn basic split method
    X_train, X_valid, y_train, y_valid = train_test_split(df,
                                                          df[y_var].astype(as_type),
                                                          test_size=validation_split,
                                                          random_state=seed)
    if test_set is True:
        X_valid, X_test, y_valid, y_test = train_test_split(X_valid,
                                                            y_valid,
                                                            test_size=test_split,
                                                            random_state=seed)
        logging.info(f'Successfully Spilt Data\nTrain: {X_train.shape}, {y_train.shape}\nValid: {X_valid.shape}, {y_valid.shape}\nTest: {X_test.shape}, {y_test.shape}')
    else:
        y_test = None
        X_test = None
        logging.info(f'Successfully Spilt Data\nTrain: {X_train.shape}, {y_train.shape}\nValid: {X_valid.shape}, {y_valid.shape}')
    id_list = X_test[identifiers] if test_set is True else X_valid[identifiers]
    logging.info(f'Size of the id_list for the hold set {id_list.shape}')
    if scaler:
        y_train = scaler.fit_transform(y_train.reset_index()[y_var[0]])
        y_train = pd.DataFrame(y_train)
        y_train.columns = [y_var]
        y_valid = scaler.transform(y_valid.reset_index()[y_var])
        y_valid = pd.DataFrame(y_valid)
        y_valid.columns = [y_var]
        if test_set is True:
            y_test = scaler.transform(y_test.reset_index()[y_var])
            y_test = pd.DataFrame(y_test)
            y_test.columns = [y_var]
    else:
        logging.info('This project relies on the query to have accurate labels with no preprocessing..')
        y_train = y_train.reset_index()[y_var]
        y_train = pd.DataFrame(y_train)
        y_train.columns = [y_var]
        y_valid = y_valid.reset_index()[y_var]
        y_valid = pd.DataFrame(y_valid)
        y_valid.columns = [y_var]
        if test_set is True:
            y_test = y_test.reset_index()[y_var]
            y_test = pd.DataFrame(y_test)
            y_test.columns = [y_var]

    if scaler:
        logging.info('saving y_var scaler to adls')
        save_sklearn_object_to_data_lake(save_object=scaler,
                                         file_name=(os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')
                                                    + models_dict[experiment_name]['y_preprocess_object_name']),
                                         adls_path=adls_path,
                                         container_name=etl_dict['azure_container'],
                                         connection_str=connection_str)

    X_train = sklearn_pipe.fit_transform(X_train)
    cols = preprocessing.get_column_names_from_transformer(sklearn_pipe)
    X_train = pd.DataFrame(X_train)
    X_train.columns = cols

    X_valid = sklearn_pipe.transform(X_valid)
    cols = preprocessing.get_column_names_from_transformer(sklearn_pipe)
    X_valid = pd.DataFrame(X_valid)
    X_valid.columns = cols
    if test_set is True:
        X_test = sklearn_pipe.transform(X_test)
        cols = preprocessing.get_column_names_from_transformer(sklearn_pipe)
        X_test = pd.DataFrame(X_test)
        X_test.columns = cols

    save_sklearn_object_to_data_lake(save_object=sklearn_pipe,
                                     file_name=(os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')
                                                + models_dict[experiment_name]['x_preprocess_object_name']),
                                     adls_path=adls_path,
                                     container_name=etl_dict['azure_container'],
                                     connection_str=connection_str)
    return X_train, X_valid, X_test, y_train, y_valid, y_test, sklearn_pipe, scaler, id_list


# %% ../../nbs/01a_Model_Utilities.ipynb 16
def preprocess_data(X_train, X_valid, X_test, sklearn_pipe):
    X_train = sklearn_pipe.fit_transform(X_train)
    cols = preprocessing.get_column_names_from_transformer(sklearn_pipe)
    X_train = pd.DataFrame(X_train)
    X_train.columns = cols

    X_valid = sklearn_pipe.transform(X_valid)
    cols = preprocessing.get_column_names_from_transformer(sklearn_pipe)
    X_valid = pd.DataFrame(X_valid)
    X_valid.columns = cols

    X_test = sklearn_pipe.transform(X_test)
    cols = preprocessing.get_column_names_from_transformer(sklearn_pipe)
    X_test = pd.DataFrame(X_test)
    X_test.columns = cols

    return X_train, X_valid, X_test, sklearn_pipe

# %% ../../nbs/01a_Model_Utilities.ipynb 18
def save_sklearn_object_to_data_lake(
    save_object, file_name, adls_path, container_name, connection_str
):
    """moves a sklearn object to azure data lake as a pickle file at a given path"""
    logging.info(
        f"Pushing Sklearn Object to Azure: {os.path.join(adls_path, file_name)}"
    )
    with open(file_name, "wb") as f:
        pickle.dump(save_object, f)
    az = FileHandling(connection_str)
    az.upload_file(
        azure_file_path=adls_path,
        local_file_path=file_name,
        container_name=container_name,
        overwrite=True,
    )
    os.unlink(file_name)
    logging.info(f"{file_name} successfully pushed to {adls_path}")

# %% ../../nbs/01a_Model_Utilities.ipynb 21
def create_stage_and_query_stage_sf(
    sf,  # Snowflake connection
    etl: dict,  # template etl input expected format
    udf_inputs: dict,  # template udf input expected format
    train_or_inference: str,  # training or inference
    experiment_name: str,  # name of experiment being ran
    indentification: list = None,
    experiment: bool = True
):
    features, udf_inputs, etl = get_yaml_dicts(['features.yaml', 'udf_inputs.yaml', 'etl.yaml'])
    stage_url = f"""azure://{etl['azure_account']}.blob.core.windows.net/{etl['azure_container']}/{etl['data_lake_path']}{(os.path.join('experiments', experiment_name)
        if experiment else os.path.join('LocalRunTest'))}""".replace(' ', '')
    stage_query = make_stage_query_generator(
        stage_name=etl["stage_name"] + etl['FY_folder'] + os.environ.get('CI_COMMIT_SHA', 'LocalRunTest'),
        url=stage_url,
        sas_token=os.environ["DATALAKE_SAS_TOKEN_SECRET"],
        file_type="parquet",
    )
    sf = snowflake_query()
    _ = sf.run_sql_str(stage_query)
    # TODO: Figure out a identification feature like season year
    # Udf grain is ECID, which is easy to get, but season year isn't obivous some thought is needed
    indentification = indentification if indentification is not None else [col.split('.')[-1] for col in udf_inputs[train_or_inference]['UDF_GRAIN']]
    columns = [col.upper() for col in features.keys()]
    query = generate_data_lake_query(stage_name=(etl["stage_name"]
                                                 + etl['FY_folder']
                                                 + os.environ.get('CI_COMMIT_SHA', 'LocalRunTest')),
                                     stage_path=train_or_inference.lower()+'_data/',
                                     columns=indentification + columns,
                                     extra_statement=None)
    logging.info(f'adls snowflake stage query {query}')
    sf = snowflake_query()
    df = sf.run_sql_str(query)
    logging.info(f'Preview dataframe queried {df.head()}')
    return df
