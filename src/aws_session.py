from __future__ import annotations

import boto3

from .config import AwsConfig



def make_session(cfg: AwsConfig) -> boto3.Session:
    if cfg.profile:
        return boto3.Session(profile_name=cfg.profile, region_name=cfg.region)
    return boto3.Session(region_name=cfg.region)
