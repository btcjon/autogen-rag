import os
from pdfdocument.document import PDFDocument

def txt_to_pdf(txt_file, pdf_file):
    with open(txt_file, 'r') as f:
        text = f.read()

    pdf = PDFDocument(pdf_file)
    pdf.init_report()
    pdf.h2('Text file content')
    pdf.p(text)
    pdf.generate()

directory = 'docs'

for filename in os.listdir(directory):
    if filename.endswith(".txt"):
        txt_file = os.path.join(directory, filename)
        pdf_file = os.path.join(directory, filename[:-4] + '.pdf')
        txt_to_pdf(txt_file, pdf_file)