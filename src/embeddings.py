from __future__ import annotations

import json

from .aws_session import make_session
from .config import AwsConfig


class BedrockEmbeddings:
    def __init__(self, cfg: AwsConfig) -> None:
        self.cfg = cfg
        self.client = make_session(cfg).client("bedrock-runtime")

    def embed_text(self, text: str) -> list[float]:
        body = json.dumps({"inputText": text})
        resp = self.client.invoke_model(
            modelId=self.cfg.embedding_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        return payload["embedding"]
