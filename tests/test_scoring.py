from job_finder.models import Job
from job_finder.scoring import score_job


def base_profile():
    return {
        "target_roles": ["Software Engineer", "Backend Engineer", "Platform Engineer"],
        "preferred_locations": ["Dublin", "Berlin", "Munich", "Remote Europe"],
        "skills": {
            "core": ["Java", "AWS", "distributed systems", "backend", "microservices"],
            "secondary": ["React", "TypeScript", "DynamoDB"],
        },
        "visa_keywords": ["visa sponsorship", "relocation support", "work permit"],
        "positive_keywords": ["distributed systems", "aws", "backend", "platform", "java"],
        "blocked_keywords": ["intern", "new grad", "engineering manager"],
        "seniority_review_keywords": ["staff", "principal"],
        "resume_versions": {
            "backend-platform": ["Java", "AWS", "distributed systems", "backend"],
            "fullstack": ["React", "TypeScript"],
        },
        "scoring_weights": {"title": 25, "skills": 35, "location": 20, "visa": 10, "company_priority": 10},
        "decision_thresholds": {"apply": 70, "review": 55},
    }


def test_good_backend_role_scores_apply():
    job = Job(
        company="ExampleCo",
        title="Senior Backend Engineer",
        location="Dublin, Ireland",
        url="https://example.com/job",
        source_type="greenhouse",
        source_slug="example",
        description="Build Java services on AWS for distributed systems. Relocation support and visa sponsorship available.",
        raw={"priority": 5},
    )
    scored = score_job(job, base_profile())
    assert scored.decision == "APPLY"
    assert scored.match_score >= 70
    assert scored.resume_version == "backend-platform"
    assert "Java" in scored.matched_skills


def test_intern_role_is_blocked():
    job = Job(
        company="ExampleCo",
        title="Software Engineer Intern",
        location="Berlin",
        url="https://example.com/job",
        source_type="lever",
        source_slug="example",
        description="Java AWS backend role",
        raw={"priority": 5},
    )
    scored = score_job(job, base_profile())
    assert scored.decision == "SKIP"
    assert scored.match_score < 40
