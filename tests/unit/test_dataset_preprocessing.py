from data.pipelines.prepare_kaggle import (
    normalize_contract,
    normalize_job_50k,
    normalize_job_60k,
    parse_money,
    stable_id,
)


def test_money_parser_handles_suffixes_and_blanks() -> None:
    assert parse_money("$2.5K+") == 2500
    assert parse_money("$35.50") == 35.5
    assert parse_money("") is None


def test_stable_id_is_deterministic_and_namespaced() -> None:
    assert stable_id("job", "source", "123") == stable_id("job", "source", "123")
    assert stable_id("job", "source", "123") != stable_id("client", "source", "123")


def test_60k_normalization_removes_url_and_redacts_pii() -> None:
    normalized = normalize_job_60k(
        {
            "Job Title": "Build a dashboard",
            "Job_URL": "https://example.test/jobs/123",
            "Description": "Email me at person@example.com and build Power BI.",
            "Category_1": "Microsoft Power BI",
            "Payment_Situation": "Payment verified",
            "New_Connects_Num": "12",
            "Payment_type": "Fixed-price",
            "Job_Cost": "$2,500",
            "Rating": "4.8",
            "Feedback_Num": "21",
        }
    )
    assert normalized is not None
    assert normalized["budget"]["max"] == 2500
    assert normalized["connects_cost"] == 12
    assert "person@example.com" not in normalized["description"]
    assert "Job_URL" not in normalized
    assert normalized["provenance"]["data_origin"] == "real_public_dataset"


def test_50k_normalization_is_explicit_temporal_real_data() -> None:
    normalized = normalize_job_50k(
        {
            "title": "Python forecast",
            "link": "https://example.test/jobs/456",
            "description": "Build a forecast.",
            "published_date": "2024-02-17 09:09:17+00:00",
            "is_hourly": "False",
            "budget": "1100",
        }
    )
    assert normalized is not None
    assert normalized["budget"] == {"min": 1100, "max": 1100, "currency": "USD"}
    assert normalized["provenance"]["source_version"] == 1


def test_contract_normalization_drops_original_identifiers() -> None:
    normalized = normalize_contract(
        {
            "job_id": "raw-job-id",
            "freelancer_id": "raw-freelancer-id",
            "job_title": "English to Chinese Translation",
            "start_date": "2024-07-08 00:20:55.228",
            "end_date": "",
            "total_hours": "3.5",
            "total_paid": "122.5",
            "hourly_rate": "35",
        }
    )
    assert normalized is not None
    assert "raw-job-id" not in str(normalized)
    assert "raw-freelancer-id" not in str(normalized)
    assert normalized["hourly_rate_usd"] == 35


def test_fixed_contract_without_hourly_rate_is_retained() -> None:
    normalized = normalize_contract(
        {
            "job_id": "fixed-job",
            "freelancer_id": "fixed-freelancer",
            "job_title": "Dashboard milestone",
            "start_date": "2024-01-01",
            "end_date": "2024-01-15",
            "total_hours": "",
            "total_paid": "500",
            "hourly_rate": "",
        }
    )
    assert normalized is not None
    assert normalized["pricing_model"] == "fixed_or_milestone"
    assert normalized["hourly_rate_usd"] is None
