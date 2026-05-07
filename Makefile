SHELL := /bin/bash

AWS_PROFILE ?= stack-research
AWS_REGION ?= us-east-2
PYTHONPATH_ROOT := ..
STACKS_DIR := stacks

.PHONY: synth deploy exp-e1 exp-e2 exp-e3 exp-e4 ingest show-tables e2-analysis

synth:
	cd $(STACKS_DIR) && uv run cdk synth

deploy:
	cd $(STACKS_DIR) && uv run cdk deploy --profile $(AWS_PROFILE)

exp-e1:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e1

exp-e2:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e2

exp-e3:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e3

exp-e4:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e4

ingest:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.ingestion.run_ingestion

show-tables:
	aws athena start-query-execution --work-group memory-lab --query-string "SHOW TABLES IN memory_lab" --query-execution-context Database=memory_lab,Catalog=AwsDataCatalog --profile $(AWS_PROFILE) --region $(AWS_REGION)

e2-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e2_drift_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab
