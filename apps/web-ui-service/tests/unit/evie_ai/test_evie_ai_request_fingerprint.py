from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from app.constants.evie_ai import (
    TestAssetReviewAction as ReviewAction,
)
from app.constants.evie_ai import (
    TestAssetSourceType as SourceType,
)
from app.policies.evie_ai.content_fingerprint import TestAssetContent as AssetContent
from app.policies.evie_ai.request_fingerprint import (
    CreateAssetFingerprintInput,
    CreateVersionFingerprintInput,
    DeleteAssetFingerprintInput,
    RestoreAssetFingerprintInput,
    RestoreHistoricalVersionFingerprintInput,
    ReviewAssetFingerprintInput,
    build_create_asset_request_fingerprint,
    build_create_version_request_fingerprint,
    build_delete_asset_request_fingerprint,
    build_restore_asset_request_fingerprint,
    build_restore_historical_version_request_fingerprint,
    build_review_asset_request_fingerprint,
)

CONTENT = AssetContent(
    title="  Cafe\u0301  ",
    precondition=" ready \r\nnext  \r",
    natural_steps=(" first  \r\n  second  ", " keep  internal "),
    expected_result=" result  ",
    priority=" P1 ",
    tags=(" smoke ", "", "回归", "smoke", "  回归 "),
)
ASSET_ID = "ta_0123456789abcdef0123456789abcdef"
VERSION_ID = "tav_0123456789abcdef0123456789abcdef"


def test_create_asset_request_fingerprint_matches_frozen_vector() -> None:
    command = CreateAssetFingerprintInput(
        source_type=SourceType.MANUAL,
        content=CONTENT,
    )

    assert build_create_asset_request_fingerprint(command) == (
        "6c994870bbc8d03fcdb030fbb27bec77c9a5245a488a1f0e2e207b9418fb3010"
    )


def test_all_six_operation_fingerprints_are_stable_and_field_sensitive() -> None:
    create_asset = CreateAssetFingerprintInput(
        source_type=SourceType.MANUAL,
        content=CONTENT,
    )
    changed_create_asset = CreateAssetFingerprintInput(
        source_type=SourceType.REQUIREMENT,
        content=CONTENT,
        requirement_id="req_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        requirement_version_id="reqv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    )
    create_version = CreateVersionFingerprintInput(
        test_asset_id=ASSET_ID,
        expected_row_version=3,
        content=CONTENT,
        reason=" edit ",
    )
    restore_version = RestoreHistoricalVersionFingerprintInput(
        test_asset_id=ASSET_ID,
        test_asset_version_id=VERSION_ID,
        expected_row_version=3,
        reason=" restore ",
    )
    review = ReviewAssetFingerprintInput(
        test_asset_id=ASSET_ID,
        test_asset_version_id=VERSION_ID,
        expected_row_version=3,
        decision=ReviewAction.APPROVE,
        comment=" good ",
        reason=None,
    )
    delete = DeleteAssetFingerprintInput(
        test_asset_id=ASSET_ID,
        expected_row_version=3,
        reason=" duplicate ",
    )
    restore = RestoreAssetFingerprintInput(
        test_asset_id=ASSET_ID,
        expected_row_version=3,
        reason=" needed ",
    )

    changed_create_version = CreateVersionFingerprintInput(
        test_asset_id=ASSET_ID,
        expected_row_version=4,
        content=CONTENT,
        reason=" edit ",
    )
    changed_restore_version = RestoreHistoricalVersionFingerprintInput(
        test_asset_id=ASSET_ID,
        test_asset_version_id=VERSION_ID,
        expected_row_version=3,
        reason=" restore another version ",
    )
    changed_review = ReviewAssetFingerprintInput(
        test_asset_id=ASSET_ID,
        test_asset_version_id=VERSION_ID,
        expected_row_version=3,
        decision=ReviewAction.REJECT,
        comment=" good ",
        reason="not approved",
    )
    changed_delete = DeleteAssetFingerprintInput(
        test_asset_id=ASSET_ID,
        expected_row_version=3,
        reason=" obsolete ",
    )
    changed_restore = RestoreAssetFingerprintInput(
        test_asset_id=ASSET_ID,
        expected_row_version=4,
        reason=" needed ",
    )

    fingerprints = (
        (
            build_create_asset_request_fingerprint(create_asset),
            build_create_asset_request_fingerprint(changed_create_asset),
        ),
        (
            build_create_version_request_fingerprint(create_version),
            build_create_version_request_fingerprint(changed_create_version),
        ),
        (
            build_restore_historical_version_request_fingerprint(restore_version),
            build_restore_historical_version_request_fingerprint(
                changed_restore_version
            ),
        ),
        (
            build_review_asset_request_fingerprint(review),
            build_review_asset_request_fingerprint(changed_review),
        ),
        (
            build_delete_asset_request_fingerprint(delete),
            build_delete_asset_request_fingerprint(changed_delete),
        ),
        (
            build_restore_asset_request_fingerprint(restore),
            build_restore_asset_request_fingerprint(changed_restore),
        ),
    )
    assert tuple(original for original, _changed in fingerprints) == (
        "6c994870bbc8d03fcdb030fbb27bec77c9a5245a488a1f0e2e207b9418fb3010",
        "4e0c60e5005a216600bd5dbb1074c48c6a1a93735d93fa304bec36036a97f575",
        "51697a6e82ec6b55a3955b0ff1383176bf467e6455d8a68e64d8d91bcc2024e3",
        "b40cbd0a9cf87e489af164855d4e9a186b48b60c1f4bf565af2dc88c1ea6152a",
        "416bd784b55e2637c3f3e75370717b2ec1624677b05ce037a77f0f330d6c40f3",
        "bbba3474c6bf269633bc2539411462165d8c52d81fd2b9a9d9739c4c5dbc3757",
    )
    assert all(original != changed for original, changed in fingerprints)


def test_scope_and_transport_fields_are_not_accepted_by_fingerprint_inputs() -> None:
    assert set(CreateAssetFingerprintInput.__dataclass_fields__) == {
        "source_type",
        "content",
        "requirement_id",
        "requirement_version_id",
    }
    for forbidden in {
        "project_code",
        "actor_or_client_id",
        "channel",
        "idempotency_key",
        "request_id",
        "correlation_id",
        "created_at",
    }:
        assert forbidden not in CreateAssetFingerprintInput.__dataclass_fields__


def test_request_fingerprint_rejects_invalid_source_and_concurrency_contracts() -> None:
    with pytest.raises(ValueError, match="Requirement source identity"):
        build_create_asset_request_fingerprint(
            CreateAssetFingerprintInput(
                source_type=SourceType.REQUIREMENT,
                content=CONTENT,
            )
        )

    with pytest.raises(ValueError, match="Manual source"):
        build_create_asset_request_fingerprint(
            CreateAssetFingerprintInput(
                source_type=SourceType.MANUAL,
                content=CONTENT,
                requirement_id="req_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                requirement_version_id="reqv_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            )
        )

    with pytest.raises(ValueError, match="expected_row_version"):
        build_delete_asset_request_fingerprint(
            DeleteAssetFingerprintInput(
                test_asset_id=ASSET_ID,
                expected_row_version=0,
                reason="delete",
            )
        )


def test_request_fingerprint_is_stable_across_process_restarts() -> None:
    service_root = Path(__file__).resolve().parents[3]
    process_code = """
from app.constants.evie_ai import TestAssetSourceType
from app.policies.evie_ai.content_fingerprint import TestAssetContent
from app.policies.evie_ai.request_fingerprint import (
    CreateAssetFingerprintInput,
    build_create_asset_request_fingerprint,
)
content = TestAssetContent(
    title='  Cafe\\u0301  ',
    precondition=' ready \\r\\nnext  \\r',
    natural_steps=(' first  \\r\\n  second  ', ' keep  internal '),
    expected_result=' result  ',
    priority=' P1 ',
    tags=(' smoke ', '', '回归', 'smoke', '  回归 '),
)
print(build_create_asset_request_fingerprint(CreateAssetFingerprintInput(
    source_type=TestAssetSourceType.MANUAL,
    content=content,
)))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(service_root)

    outputs = {
        subprocess.check_output(
            [sys.executable, "-c", process_code],
            cwd=service_root,
            env=environment,
            text=True,
        ).strip()
        for _ in range(2)
    }

    assert outputs == {
        "6c994870bbc8d03fcdb030fbb27bec77c9a5245a488a1f0e2e207b9418fb3010"
    }
