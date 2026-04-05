import io
from datetime import datetime

import xlsxwriter  # TODO: replace with openpyxl
from django.http import HttpResponse


def export_abstract_event_changes(abs_event_changes) -> HttpResponse|None:
    """Makes XLS file for given AbstractEventChanges
    """

    if not abs_event_changes.exists():
        return None

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()

    column_names = ["ДАТА СОЗДАНИЯ", "ГРУППА", "ДЕНЬ НЕДЕЛИ/УЧ. ЧАС", "ПРЕДМЕТ", "ИЗМЕНЕНО", "БЫЛО", "СТАЛО"]
    for i in range(len(column_names)):
        worksheet.write(0, i, column_names[i])

    row = 2
    for aec in abs_event_changes:
        for changes in aec.export():
            for i in range(len(changes)):
                worksheet.write(row, i, changes[i])

            row += 1

        row += 1

    worksheet.autofit()
    workbook.close()

    output.seek(0)

    response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f"attachment; filename={datetime.now().strftime('%d-%m-%Y_%H-%M-%S')}.xlsx"

    return response