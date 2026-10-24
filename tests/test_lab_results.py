from Backend.OCR.lab_results import parse_lab_results


def test_parse_flattened_differential_results_and_keep_orphan_range():
    raw = """4.0-10.0
Coulter Principle
Polymorphs
55.0
%
40-80
Flowcytometry
Lymphocytes
38.5
%
20-40"""

    parsed = parse_lab_results(raw)

    assert [(row["test"], row["value"], row["unit"], row["reference_range"])
            for row in parsed["results"]] == [
        ("Polymorphs", 55.0, "%", "40-80"),
        ("Lymphocytes", 38.5, "%", "20-40"),
    ]
    assert [row["status"] for row in parsed["results"]] == ["normal", "normal"]
    assert "4.0-10.0" in parsed["unparsed"]
    assert parsed["summary"] == {"total": 2, "abnormal": 0}


def test_parse_comparator_ranges_and_methods():
    parsed = parse_lab_results("Impedance\nHemoglobin\n11.0\ng/dL\n12.0-16.0\nGlucose\n6.2\nmmol/L\n< 5.6")

    assert parsed["results"][0]["status"] == "low"
    assert parsed["results"][0]["method"] == "Impedance"
    assert parsed["results"][1]["status"] == "high"
    assert parsed["summary"]["abnormal"] == 2
