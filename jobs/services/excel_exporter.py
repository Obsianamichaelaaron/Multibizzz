import io
import re
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


def sanitize_filename_part(text: str) -> str:
    """Sanitize strings for safe filenames."""
    if not text:
        return "Job"
    sanitized = re.sub(r'[^a-zA-Z0-9_\-]', '_', text.strip())
    return re.sub(r'_+', '_', sanitized)[:40].strip('_')


def generate_candidates_excel(job, applications_qs, filename=None):
    """
    Generates a corporate-styled Excel spreadsheet (.xlsx) containing candidate evaluations
    (both Qualified and Not Qualified), match scores, skills breakdown, education, and notes.

    Returns:
        tuple: (BytesIO buffer with .xlsx content, filename_str)
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Candidate Evaluations"

    # Color Palette & Styles
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Deep Navy
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    title_font = Font(name="Calibri", size=15, bold=True, color="1E3A8A")
    meta_font = Font(name="Calibri", size=10, italic=False, color="475569")
    meta_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")
    
    data_font = Font(name="Calibri", size=10, color="1E293B")
    data_bold = Font(name="Calibri", size=10, bold=True, color="1E293B")
    
    # Status styling
    status_qualified_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # Soft Emerald
    status_qualified_font = Font(name="Calibri", size=10, bold=True, color="15803D")

    status_under_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # Soft Amber
    status_under_font = Font(name="Calibri", size=10, bold=True, color="92400E")

    status_not_fill = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid") # Soft Rose
    status_not_font = Font(name="Calibri", size=10, bold=True, color="991B1B")

    zebra_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    thin_border_side = Side(style="thin", color="E2E8F0")
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    
    header_border_side = Side(style="medium", color="1E3A8A")
    header_border = Border(left=thin_border_side, right=thin_border_side, top=header_border_side, bottom=header_border_side)

    center_align = Alignment(horizontal="center", vertical="center", wrap_text=False)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=False)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=False)

    # 1. Top Metadata Banner
    company_name = job.employer.display_name if job.employer else "Multibiz Client"
    export_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    apps_list = list(applications_qs)
    total_count = len(apps_list)
    qualified_count = sum(1 for a in apps_list if a.qualification_status == 'qualified')
    under_count = sum(1 for a in apps_list if a.qualification_status == 'under_qualified')
    not_qualified_count = sum(1 for a in apps_list if a.qualification_status == 'not_qualified')

    ws.merge_cells("A1:L1")
    ws["A1"] = f"MULTIBIZ CANDIDATE EVALUATION REPORT — {job.title.upper()}"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.merge_cells("A2:L2")
    ws["A2"] = (
        f"Employer: {company_name}  |  Job Location: {job.location}  |  "
        f"Export Date: {export_time_str}  |  Total Candidates: {total_count} "
        f"(Qualified: {qualified_count}, Under Qualified: {under_count}, Not Qualified: {not_qualified_count})"
    )
    ws["A2"].font = meta_font
    ws["A2"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[2].height = 20

    ws.append([]) # Blank row 3
    ws.row_dimensions[3].height = 10

    # 2. Table Headers
    headers = [
        "Rank",
        "Candidate Name",
        "Email Address",
        "Phone / Contact",
        "Job Applied For",
        "Qualification Status",
        "Match Score",
        "Matched Skills",
        "Missing / Desired Skills",
        "Education Level",
        "Experience",
        "Application Date",
        "Evaluation Summary / Notes"
    ]

    header_row_idx = 4
    ws.append(headers)
    ws.row_dimensions[header_row_idx].height = 26

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align
        cell.border = header_border

    # 3. Data Rows (Both Qualified and Not Qualified)
    job_skills_list = job.get_skills_list()
    job_skills_set = set(s.lower().strip() for s in job_skills_list)

    # Sort candidates by match score descending
    sorted_apps = sorted(apps_list, key=lambda a: (0 if a.qualification_status == 'qualified' else (1 if a.qualification_status == 'under_qualified' else 2), -float(a.match_score or 0)))

    for rank_idx, app in enumerate(sorted_apps, start=1):
        current_row = header_row_idx + rank_idx
        applicant = app.applicant
        user = applicant.user

        cand_skills = applicant.get_skills_list()
        matched = [s for s in cand_skills if s.lower().strip() in job_skills_set]
        missing = [s for s in job_skills_list if s.lower().strip() not in set(cs.lower().strip() for cs in cand_skills)]

        # Qualification Label
        if app.qualification_status == 'qualified':
            qual_label = "QUALIFIED"
            qual_fill = status_qualified_fill
            qual_font = status_qualified_font
        elif app.qualification_status == 'under_qualified':
            qual_label = "UNDER QUALIFIED"
            qual_fill = status_under_fill
            qual_font = status_under_font
        else:
            qual_label = "NOT QUALIFIED"
            qual_fill = status_not_fill
            qual_font = status_not_font

        row_fill = zebra_fill if rank_idx % 2 == 0 else white_fill
        score_val = float(app.match_score or 0)

        row_data = [
            f"#{rank_idx}",
            user.full_name,
            user.email,
            user.phone or "N/A",
            job.title,
            qual_label,
            f"{int(score_val)}%",
            ", ".join(matched) if matched else "None",
            ", ".join(missing) if missing else "None",
            applicant.education_level or "Not specified",
            f"{applicant.experience_years} yrs" if applicant.experience_years is not None else "0 yrs",
            app.applied_at.strftime("%Y-%m-%d") if app.applied_at else "-",
            app.qualification_reason or f"Assessed match: {int(score_val)}%"
        ]

        ws.append(row_data)
        ws.row_dimensions[current_row].height = 22

        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = cell_border
            cell.fill = row_fill
            cell.font = data_font
            cell.alignment = left_align

            # Specific column alignments & styling
            if col_idx == 1: # Rank
                cell.alignment = center_align
                cell.font = data_bold
            elif col_idx == 2: # Candidate Name
                cell.font = data_bold
            elif col_idx in (4, 11, 12): # Phone, Exp, Date
                cell.alignment = center_align
            elif col_idx == 6: # Qualification Status
                cell.fill = qual_fill
                cell.font = qual_font
                cell.alignment = center_align
            elif col_idx == 7: # Match score
                cell.alignment = center_align
                cell.font = data_bold

    # 4. Auto-fit column widths with padding
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        
        # Calculate max string length in column (skipping title rows)
        for cell in col:
            if cell.row in (1, 2, 3):
                continue
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # Specific fixed column bounds for optimal viewing
    ws.column_dimensions["A"].width = 8   # Rank
    ws.column_dimensions["B"].width = 24  # Name
    ws.column_dimensions["C"].width = 26  # Email
    ws.column_dimensions["D"].width = 16  # Phone
    ws.column_dimensions["E"].width = 25  # Job
    ws.column_dimensions["F"].width = 18  # Qualification Status
    ws.column_dimensions["G"].width = 14  # Match Score
    ws.column_dimensions["H"].width = 28  # Matched Skills
    ws.column_dimensions["I"].width = 28  # Missing Skills
    ws.column_dimensions["J"].width = 20  # Education
    ws.column_dimensions["K"].width = 14  # Experience
    ws.column_dimensions["L"].width = 16  # Date
    ws.column_dimensions["M"].width = 40  # Notes

    # Generate filename if not provided
    if not filename:
        clean_job = sanitize_filename_part(job.title)
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        filename = f"Candidates_{clean_job}_{date_str}.xlsx"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    return output, filename
