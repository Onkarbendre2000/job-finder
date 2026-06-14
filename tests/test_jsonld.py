from job_finder.jsonld import extract_job_postings, job_location_from_jsonld, job_title_from_jsonld


def test_extracts_job_posting_from_jsonld():
    html = '''
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "JobPosting",
        "title": "Senior Backend Engineer",
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Berlin",
            "addressCountry": "Germany"
          }
        }
      }
      </script>
    </head></html>
    '''
    jobs = extract_job_postings(html)
    assert len(jobs) == 1
    assert job_title_from_jsonld(jobs[0]) == "Senior Backend Engineer"
    assert "Berlin" in job_location_from_jsonld(jobs[0])
    assert "Germany" in job_location_from_jsonld(jobs[0])
