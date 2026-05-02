"""
providers/aws/model_development/sagemaker_tracker.py
Amazon SageMaker Experiments — AbstractExperimentTracker implementation.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from sagemaker.experiments.run import Run
from sagemaker.session import Session

from core.interfaces.experiment_tracker import AbstractExperimentTracker
from providers.aws.config.settings import get_aws_settings


class SageMakerTracker(AbstractExperimentTracker):
    """
    AbstractExperimentTracker backed by Amazon SageMaker Experiments.
    Each context-manager call opens a SageMaker Run under the configured experiment.
    """

    def __init__(self) -> None:
        s = get_aws_settings()
        self._experiment_name = s.sagemaker_experiment_name
        self._session = Session()
        self._run: Run | None = None

    @contextmanager
    def run(self, run_name: str, tags: dict[str, str] | None = None) -> Generator["SageMakerTracker", None, None]:
        with Run(
            experiment_name=self._experiment_name,
            run_name=run_name,
            sagemaker_session=self._session,
        ) as sm_run:
            self._run = sm_run
            if tags:
                for k, v in tags.items():
                    sm_run.log_parameter(k, v)
            yield self
        self._run = None

    def log_params(self, params: dict[str, Any]) -> None:
        if self._run:
            for k, v in params.items():
                self._run.log_parameter(k, v)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        if self._run:
            for k, v in metrics.items():
                self._run.log_metric(k, v, step=step)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        if self._run:
            self._run.log_file(local_path, name=artifact_path or local_path)

    def set_tag(self, key: str, value: str) -> None:
        if self._run:
            self._run.log_parameter(key, value)
