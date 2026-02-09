"""Assembles prompts from YAML-stored sections for each pipeline stage."""

import re
from pathlib import Path
from prompts.prompt_manager import load_prompt, assemble_prompt_text


def build_report_prompt(company_name: str,
                        business_desc_content: str,
                        target_md_file_obj,
                        target_pdf_file_objs: list,
                        example_files_info: list) -> list:
    """Build the full prompt_contents list for Stage 3 (report generation).

    Returns a list of mixed content (strings + file objects) ready for
    client.models.generate_content(contents=...).
    """
    # Load prompt sections from YAML
    instructions = load_prompt("report_instructions")
    inst_sections = instructions.get("sections", {})

    # Role and context
    role_text = inst_sections.get("role_definition", {}).get("content", "")
    guidance_preamble = inst_sections.get("guidance_preamble", {}).get("content", "")
    target_preamble = inst_sections.get("target_inputs_preamble", {}).get("content", "")
    examples_preamble = inst_sections.get("examples_preamble", {}).get("content", "")
    output_format = inst_sections.get("output_format", {}).get("content", "")
    section_conclusions = inst_sections.get("section_conclusions", {}).get("content", "")
    mandatory_calcs = inst_sections.get("mandatory_calculations", {}).get("content", "")
    overall_conclusion = inst_sections.get("overall_conclusion", {}).get("content", "")
    citation_rules = inst_sections.get("citation_rules", {}).get("content", "")

    # Replace {company_name} placeholder in overall conclusion
    overall_conclusion = overall_conclusion.replace("{company_name}", company_name)

    # Assemble the two guidance documents from their YAML sections
    guidance1_text = assemble_prompt_text("fin_condition_assessment_synthesis")
    guidance2_text = assemble_prompt_text("financial_health_diagnostics")

    # Build the prompt_contents list
    prompt_contents = [
        role_text,
        f"The report is for **{company_name}**.",

        "\n### PRIMARY GUIDANCE (MANDATORY ADHERENCE) ###",
        guidance_preamble,
        "**Guidance Document 1: 'Financial Condition Assessment Synthesis'**",
        guidance1_text,
        "\n**Guidance Document 2: 'Financial Health Diagnostics'**",
        guidance2_text,

        "\n### TARGET COMPANY INPUTS FOR ANALYSIS ###",
        target_preamble,
        f"1. **Company Business Description**: Use this text for the company overview section.",
        business_desc_content,
        f"2. **Financial Ratios**: The primary quantitative data for your analysis.",
        target_md_file_obj,
    ]

    if target_pdf_file_objs:
        prompt_contents.append(
            f"\n3. **Audited Financial Statements ({len(target_pdf_file_objs)} PDF file(s))**: "
            "Use these to verify data, understand the context, and perform required calculations "
            "if data is missing from the ratios file."
        )
        prompt_contents.extend(target_pdf_file_objs)
    else:
        prompt_contents.append(
            "\n3. **Audited Financial Statements**: No PDFs were provided. "
            "Base your entire analysis on the provided ratio file and business description."
        )

    if example_files_info:
        prompt_contents.append("\n### FEW-SHOT LEARNING EXAMPLES ###")
        prompt_contents.append(examples_preamble)
        for ex in example_files_info:
            prompt_contents.extend([
                f"\n**Example Set: {ex['name']}**",
                "Input Ratio File:",
                ex['md_file_obj'],
                "Final Report Example:",
                ex['pdf_file_obj'],
            ])

    prompt_contents.extend([
        "\n### REPORT GENERATION INSTRUCTIONS ###",
        f"1. **Output Format**: {output_format}",
        f"2. **Definitive Section Conclusions**: {section_conclusions}",
        f"3. **Mandatory Calculations (If data is missing)**:\n{mandatory_calcs}",
        f"4. **Overall Conclusion (Section 5)**: {overall_conclusion}",
        f"5. **{citation_rules}**",
        f"\nNow, generate the complete HTML Financial Condition Assessment Report for **{company_name}**.",
    ])

    return prompt_contents


def build_audit_prompt(html_report_content: str,
                       llm_risk_research_text: str,
                       report_filename: str) -> list:
    """Build the prompt for Stage 4 (audit review)."""
    audit = load_prompt("audit_criteria")
    sections = audit.get("sections", {})

    role = sections.get("role_definition", {}).get("content", "")
    output_fmt = sections.get("output_format", {}).get("content", "")

    # Build criteria text from individual sections
    criteria_keys = ["bias", "hallucination", "incoherence", "verbosity",
                     "pii", "chain_of_thought", "formatting", "other_failures"]
    criteria_items = []
    for i, key in enumerate(criteria_keys, 1):
        sec = sections.get(key, {})
        title = sec.get("title", f"{i}. {key}")
        content = sec.get("content", "")
        criteria_items.append(f"{i}.  **{title.split('. ', 1)[-1] if '. ' in title else title}:** {content}")

    prompt_contents = [
        role,

        "\n**LLM Model Risks Research (Context):**",
        "--- BEGIN LLM RISKS RESEARCH ---",
        llm_risk_research_text,
        "--- END LLM RISKS RESEARCH ---",

        "\n**HTML Financial Report to Review:**",
        "--- BEGIN HTML REPORT CONTENT ---",
        html_report_content,
        "--- END HTML REPORT CONTENT ---",

        "\n**Audit Instructions:**",
        "Please review the 'HTML Financial Report Content' thoroughly for the following "
        "potential LLM failures. For each category, provide specific examples or quotes "
        "from the report if issues are found. If no significant issues are detected in "
        "a category, explicitly state that. Your analysis should be grounded in the "
        "principles and risks outlined in the 'LLM Model Risks Research (Context)'.",
    ]
    prompt_contents.extend(criteria_items)

    prompt_contents.extend([
        "\n**Output Format:**",
        output_fmt,
        f"\nGenerate the complete HTML audit review report for the financial report "
        f"originally named '{report_filename}' now."
    ])

    return prompt_contents


def build_comparison_prompt(llm_report_content: str,
                            human_report_file_obj,
                            audited_statements_file_obj) -> list:
    """Build the prompt for Stage 5 (human vs LLM comparison)."""
    prompt_parts = [
        "You are an expert AI Model Auditor specializing in financial report analysis. "
        "Your task is to perform a side-by-side comparison and evaluation of two financial "
        "condition reports:",
        "1.  A 'Human-Created Financial Report' (provided as a document).",
        "2.  An 'LLM-Generated Financial Report' (provided as HTML text).",
        "You must also use the 'Audited Financial Statements' (provided as a PDF document) "
        "as a ground truth reference, especially for factual accuracy and input data verification.",
        "Your evaluation should specifically focus on 'Section 4' and 'Section 5' of each report. "
        "If these exact section titles are not present, infer the content of typical sections "
        "related to financial performance review, balance sheet analysis, cash flow, key ratios, "
        "future outlook, or risk assessment for comparison.",

        "\n**Evaluation Criteria:**",
        "1.  **Validity of Conclusions:** Assess if the conclusions drawn in the relevant sections "
        "of each report are sound, well-reasoned, and logically supported.",
        "2.  **Depth of Assessment:** Evaluate the thoroughness and detail of the analysis.",
        "3.  **Relevance of Inputs Used:** Examine if the information and data points utilized "
        "are pertinent to the financial condition assessment.",
        "4.  **Omissions/Inconsistencies:** Identify any significant omissions or internal "
        "inconsistencies within each report, and between the two reports.",
        "5.  **Input Data Reference Errors (compared to Audited Financial Statements):** "
        "Cross-reference specific figures mentioned in both reports with the Audited Financial "
        "Statements. Note any discrepancies.",

        "\n**Human-Created Financial Report (Document):**",
        human_report_file_obj,
        "\n**LLM-Generated Financial Report (HTML Content):**",
        llm_report_content,
        "\n**Audited Financial Statements (PDF Document):**",
        audited_statements_file_obj,

        "\n**Output Format:**",
        "Generate a structured **HTML report** with title 'Comparative Analysis of Financial "
        "Reports: Human vs. LLM Generated'. Create two main sections: 'Section 4 Comparison' "
        "and 'Section 5 Comparison'. Use `<h3>` for each evaluation criterion. Use `<blockquote>` "
        "for quotes.",

        "\nGenerate the complete HTML comparison report now."
    ]

    return prompt_parts
