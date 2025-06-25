import os
import glob
import fitz  # PyMuPDF
from PIL import Image

class PDFConverter:
    def __init__(self, input_dir, output_dir, dpi=300, header_points=79):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.dpi = dpi
        self.header_pixels = int(header_points * self.dpi / 72)

    def run(self):
        """入力ディレクトリのPDFをTIFFに変換し、ヘッダーを除去する"""
        pdf_files = glob.glob(os.path.join(self.input_dir, "*.pdf"))
        for pdf_path in pdf_files:
            try:
                self._convert_and_crop(pdf_path)
            except Exception as e:
                print(f"Error converting {pdf_path}: {e}")

    def _convert_and_crop(self, pdf_path):
        """単一のPDFを変換・クロップして保存する"""
        doc = fitz.open(pdf_path)
        page = doc[0]

        mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
        pix = page.get_pixmap(matrix=mat)

        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # ヘッダーを除去
        img_no_header = img.crop((0, self.header_pixels, img.width, img.height))

        # TIFFとして保存
        basename = os.path.basename(pdf_path)
        filename_no_ext = os.path.splitext(basename)[0]
        output_path = os.path.join(self.output_dir, f"{filename_no_ext}.tiff")
        
        img_no_header.save(output_path, format='TIFF', compression='tiff_lzw')
        doc.close()
