import gradio as gr
import numpy as np
import sqlite3
from datetime import datetime
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import openpyxl
import os
import cv2
from ultralytics import YOLO

# Загружаем модель YOLOv5s (модель из ultralytics)
model = YOLO('yolov5s.pt')

db_file = 'history.db'

def init_db():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            datetime TEXT,
            skateboard_count INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def detect(image):
    if isinstance(image, Image.Image):
        image = np.array(image)

    results = model(image)
    result = results[0]  # <-- ВАЖНО: берём первый результат из списка

    names = result.names
    boxes = result.boxes
    class_ids = boxes.cls.cpu().numpy().astype(int)
    labels = [names[i] for i in class_ids]

    skateboard_count = labels.count("skateboard")

    # Рендер результата
    rendered = result.plot()
    output_img = cv2.cvtColor(rendered, cv2.COLOR_BGR2RGB)

    # Сохраняем результат в БД
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filename = f"image_{datetime.now().strftime('%H%M%S')}.jpg"

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO history (filename, datetime, skateboard_count) VALUES (?, ?, ?)',
                   (filename, timestamp, skateboard_count))
    conn.commit()
    conn.close()

    return output_img, get_stats_and_history()


def get_stats_and_history():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT filename, datetime, skateboard_count FROM history ORDER BY id DESC LIMIT 5')
    rows = cursor.fetchall()

    cursor.execute('SELECT COUNT(*), AVG(skateboard_count), MAX(skateboard_count) FROM history')
    total, avg, max_count = cursor.fetchone()
    conn.close()

    if total == 0:
        return "История пуста."

    avg = round(avg, 2) if avg is not None else 0

    history_html = "<b>Последние 5 обработок:</b><br><table border='1' style='border-collapse:collapse'><tr><th>Файл</th><th>Дата</th><th>Скейтборды</th></tr>"
    for row in rows:
        history_html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>"
    history_html += "</table><br>"

    stats_html = f"""
    <b>Статистика:</b><br>
    Всего изображений: {total}<br>
    Среднее число скейтбордов: {avg}<br>
    Рекорд (максимум скейтбордов): {max_count}<br>
    """

    return history_html + stats_html

def clear_history():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM history')
    conn.commit()
    conn.close()
    return None, "История очищена."

def export_pdf():
    pdf_file = "report.pdf"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT filename, datetime, skateboard_count FROM history ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()

    c = canvas.Canvas(pdf_file, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Отчёт по скейтбордам")

    c.setFont("Helvetica", 12)
    y = height - 100
    if not rows:
        c.drawString(50, y, "Нет данных.")
    else:
        for row in rows:
            line = f"Файл: {row[0]} | Дата: {row[1]} | Скейтборды: {row[2]}"
            c.drawString(50, y, line)
            y -= 20
            if y < 50:
                c.showPage()
                y = height - 50
    c.save()
    return pdf_file

def export_excel():
    xls_file = "report.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Файл", "Дата", "Скейтборды"])

    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    cursor.execute('SELECT filename, datetime, skateboard_count FROM history ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        ws.append(row)

    wb.save(xls_file)
    return xls_file

with gr.Blocks() as app:
    gr.Markdown("# 🎯 Контроль катания на скейтборде")

    with gr.Tab("Обработка изображений"):
        with gr.Row():
            with gr.Column():
                img_input = gr.Image(type="pil", label="Загрузите изображение")
                btn = gr.Button("Обработать")
                clear_btn = gr.Button("Очистить историю")
            with gr.Column():
                img_output = gr.Image(type="numpy", label="Результат")
                stats_output = gr.HTML(label="История и статистика")

        btn.click(detect, inputs=img_input, outputs=[img_output, stats_output])
        clear_btn.click(clear_history, inputs=None, outputs=[img_output, stats_output])

    with gr.Tab("Отчёты"):
        gr.Markdown("Скачать отчёты с историей обработки:")
        pdf_btn = gr.Button("Скачать PDF")
        excel_btn = gr.Button("Скачать Excel")
        pdf_file = gr.File()
        excel_file = gr.File()

        pdf_btn.click(export_pdf, outputs=pdf_file)
        excel_btn.click(export_excel, outputs=excel_file)

if __name__ == "__main__":
    print("🟢 App started")
    app.launch(server_name="0.0.0.0", server_port=7860)


