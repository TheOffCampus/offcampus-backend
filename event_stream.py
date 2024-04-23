import sagemaker
from sagemaker.feature_store.feature_group import FeatureGroup
import boto3
import json
import pandas as pd
from time import gmtime, strftime, time
import time
from parameter_store import ParameterStore


role = sagemaker.get_execution_role()
sagemaker_session = sagemaker.Session()
default_bucket = sagemaker_session.default_bucket()
region = sagemaker_session.boto_region_name
s3_client = boto3.client('s3', region_name=region)

ps = ParameterStore(verbose=False)
ps.set_namespace('feature-store-workshop')

prefix = 'recsys-feature-store'

fs_prefix = 'recsys-'
current_timestamp = strftime('%m-%d-%H-%M', gmtime())
users_feature_group_name = f'{fs_prefix}users-fg-{current_timestamp}'
apartments_feature_group_name = f'{fs_prefix}apartments-fg-{current_timestamp}'
click_stream_historical_feature_group_name = f'{fs_prefix}click-stream-historical-fg-{current_timestamp}'

ps.create({'users_feature_group_name': users_feature_group_name,
           'apartments_feature_group_name': apartments_feature_group_name,
           'click_stream_historical_feature_group_name': click_stream_historical_feature_group_name})