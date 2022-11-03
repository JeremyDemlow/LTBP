# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/01a_Model_Utilities_Custom.ipynb.

# %% auto 0
__all__ = ['evaluate', 'send_holdout_results_to_sf', 'move_dev_holdout_table_to_prod_location']

# %% ../../nbs/01a_Model_Utilities_Custom.ipynb 3
from data_system_utilities.azure.storage import FileHandling

from ..data.utils import snowflake_query

from sklearn import metrics
from rfpimp import *  # noqa:
from matplotlib import pyplot as plt

import os
import logging
import datetime as dt
import scikitplot

# %% ../../nbs/01a_Model_Utilities_Custom.ipynb 4
def evaluate(model,
             X_valid,
             y_valid,
             y_var,
             feature_importance: bool = True,
             plot: bool = False):
    """
    Utlity to give experiment table information about the model
    this is fully customizable and can be changed to be regression
    RMSE, R2, MSE for example and changing the columns this function
    isn't a dynamic function it needs to be written for a specific use
    case.

    Args:
    * model (classifer): sklearn model for this
    * X_valid (np.array): Validation set Traing
    * y_valid (np.array): Actuals for Validation
    * y_var (str): variable name being predicted

    Returns:
    * dict: dependent on return statement
    """
    y_pred_proba = model.predict_proba(X_valid)
    y_pred = model.predict(X_valid)
    auc = metrics.roc_auc_score(y_valid, y_pred_proba[:, 1])
    acc = metrics.accuracy_score(y_valid, y_pred)
    bacc = metrics.balanced_accuracy_score(y_valid, y_pred)
    columns = ['auc', 'acc', 'bacc']
    logging.info(f'Variable(s) of interest {y_var} AUC: {auc:.3f}    Accuracy: {acc:.3f}    Balanced Accuracy: {bacc:.3f}')
    if feature_importance:
        fi_permutation = importances(model, X_valid, y_valid)  # noqa:
        fi_permutation = (fi_permutation
                          .reset_index()
                          .rename({'Feature': 'COLS', 'Importance': 'IMP'}, axis=1))
        logging.info(f'Feature Importance df: \n {fi_permutation}')
    if plot:
        scikitplot.metrics.plot_confusion_matrix(y_valid,
                                                 y_pred,
                                                 figsize=(5, 5))
        plt.show()
        scikitplot.metrics.plot_roc(y_valid,
                                    y_pred_proba,
                                    figsize=(5, 5))
        plt.show()

        plt.hist(y_pred, label='prediction', alpha=0.5)
        plt.hist(y_valid, label='true', alpha=0.5)
        plt.legend()
    return auc, acc, bacc, columns, y_pred_proba, y_pred, fi_permutation if feature_importance else None

# %% ../../nbs/01a_Model_Utilities_Custom.ipynb 5
def send_holdout_results_to_sf(sf,
                               id_list: list,
                               probs,
                               experiment,
                               experiment_name,
                               etl_dict,
                               model_dict,
                               drop_table: bool = False
                               ):
    hold_out_df = pd.DataFrame(id_list)
    hold_out_df['PROBABILITY'] = probs[:, 1]
    hold_out_df['DATECREATED'] = dt.datetime.today().strftime('%Y-%m-%d %H:%M:%S')
    hold_out_df['EXP_COMMIT_CI_SHA'] = experiment_name+'_'+os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')
    logging.info(f'hold out data preview going to snowflake {hold_out_df.head(3)}')
    sf = snowflake_query()
    if drop_table:
        sf.run_sql_str(f"DROP TABLE {model_dict['hold_out_table']}")
    sf.infer_to_snowflake(hold_out_df,
                          table_name=model_dict['hold_out_table'])
    logging.info('saving test prediction file')
    hold_out_df.to_csv(f"holdout_{experiment_name}{os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')}.csv", index=False)
    adls_path = os.path.join((os.path.join(etl_dict['data_lake_path'], 'experiments', experiment_name)
                              if experiment
                              else os.path.join(
                                  etl_dict['data_lake_path'],
                                  os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')))
                             , 'holdout_results/', model_dict[experiment_name]['model_trainer'])+'/'
    logging.info(f'sending prediction file to azure to {adls_path}')
    az = FileHandling(os.environ[model_dict['connection_str']])
    _ = az.upload_file(
        azure_file_path=adls_path,
        local_file_path=f"holdout_{experiment_name}{os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')}.csv",
        container_name=etl_dict["azure_container"],
        overwrite=True,
    )
    os.unlink(f"holdout_{experiment_name}{os.environ.get('CI_COMMIT_SHA', 'LocalRunNBS')}.csv")

# %% ../../nbs/01a_Model_Utilities_Custom.ipynb 6
def move_dev_holdout_table_to_prod_location(sf,
                                            exp):
    logging.info('Replacing Prod HoldOut With Newest Promoted')
    sf.run_str_query(f"""
                      CREATE OR REPLACE TABLE MACHINELEARNINGOUTPUTS.ltbp.{exp['holdout_tb_name']} AS
                      SELECT * FROM MACHINELEARNINGOUTPUTS.DEV.{exp['holdout_tb_name']};
                      """)
