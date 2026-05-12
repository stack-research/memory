SHELL := /bin/bash

AWS_PROFILE ?= stack-research
AWS_REGION ?= us-east-2
PYTHONPATH_ROOT := ..
STACKS_DIR := stacks

.PHONY: synth deploy exp-e1 exp-e2 exp-e3 exp-e4 exp-e5 exp-e6 exp-e7 exp-e8 exp-e9 exp-e10 exp-e11 exp-e12 ingest ingest-preflight show-tables e2-analysis e5-analysis e9-analysis e10-analysis e11-analysis e12-analysis phase4-audit phase5-audit phase6-audit phase6-regression lab-regression e9-e12-regression implicit-regression implicit-regression-aws im-trigger-analysis im-contamination-analysis im-replay-diff im-l im-m im-n im-o im-p im-q axis-dominance-audit

synth:
	cd $(STACKS_DIR) && uv run cdk synth

diff:
	cd $(STACKS_DIR) && uv run cdk diff --profile $(AWS_PROFILE)

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

exp-e5:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e5

exp-e6:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e6

exp-e7:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e7

exp-e8:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e8

exp-e9:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e9

exp-e10:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e10

exp-e11:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e11

exp-e12:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.run_experiment e12

ingest:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.ingestion.run_ingestion

ingest-preflight:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.ingestion.preflight

show-tables:
	aws athena start-query-execution --work-group memory-lab --query-string "SHOW TABLES IN memory_lab" --query-execution-context Database=memory_lab,Catalog=AwsDataCatalog --profile $(AWS_PROFILE) --region $(AWS_REGION)

e2-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e2_drift_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

e5-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e5_promotion_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

e9-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e9_eligibility_pressure_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

e10-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e10_reconsolidation_stability_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

e11-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e11_promotion_forgetting_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

e12-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/e12_poison_resilience_analysis.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

phase4-audit:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/phase4_policy_audit.sql --database memory_lab --catalog $${AWS_ATHENA_S3TABLES_CATALOG:-s3tablescatalog/memory-lab-lineage-table} --workgroup memory-lab

phase5-audit:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/phase5_replay_hardening_audit.sql --database memory_lab --catalog $${AWS_ATHENA_S3TABLES_CATALOG:-s3tablescatalog/memory-lab-lineage-table} --workgroup memory-lab

phase6-audit:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/phase6_attack_surface_audit.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

phase6-regression:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.phase6_attack_surface_regression

lab-regression:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.lab_regression

e9-e12-regression:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.e9_e12_regression

implicit-regression:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_regression

implicit-regression-aws:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_aws_lineage_replay

im-trigger-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/im_trigger_metrics.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

im-contamination-analysis:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/im_contamination_metrics.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

im-replay-diff:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/im_replay_diff.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab

im-l:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_l_uncertainty_gate_modes

im-m:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_m_provenance_decay

im-n:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_n_recall_degradation

im-o:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_o_claim_implausibility

im-p:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_p_default_mode_decision

im-q:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.implicit.im_q_traffic_evidence

axis-dominance-audit:
	cd $(STACKS_DIR) && AWS_PROFILE=$(AWS_PROFILE) AWS_REGION=$(AWS_REGION) PYTHONPATH=$(PYTHONPATH_ROOT) uv run python -m src.experiments.run_sql_file ../src/experiments/sql/axis_dominance_audit.sql --database memory_lab --catalog AwsDataCatalog --workgroup memory-lab
