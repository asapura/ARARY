import unittest
from unittest.mock import patch, MagicMock
import os
import glob

from pipeline.convert import PDFConverter

class TestPDFConverter(unittest.TestCase):

    def setUp(self):
        """テストの前に一時的なディレクトリを作成"""
        self.input_dir = "/tmp/test_raw"
        self.output_dir = "/tmp/test_tiff"
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def tearDown(self):
        """テストの後に一時的なディレクトリとファイルを削除"""
        for f in glob.glob(os.path.join(self.input_dir, "*")):
            os.remove(f)
        for f in glob.glob(os.path.join(self.output_dir, "*")):
            os.remove(f)
        os.rmdir(self.input_dir)
        os.rmdir(self.output_dir)

    # @unittest.skip("Not implemented yet")
    @patch('pipeline.convert.fitz')
    @patch('pipeline.convert.Image')
    def test_convert_single_pdf(self, mock_image, mock_fitz):
        """1つのPDFがTIFFに正しく変換されるか (モックを使用)"""
        # --- モックの設定 ---
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.width, mock_pix.height, mock_pix.samples = 100, 100, b''
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__.return_value = mock_page # doc[0] をモック
        mock_fitz.open.return_value = mock_doc

        mock_img = MagicMock()
        mock_image.frombytes.return_value = mock_img

        # --- 準備 ---
        dummy_pdf_path = os.path.join(self.input_dir, "test.pdf")
        with open(dummy_pdf_path, "w") as f: f.write("dummy")

        # --- 実行 ---
        converter = PDFConverter(self.input_dir, self.output_dir)
        converter.run()

        # --- 検証 ---
        expected_tiff_path = os.path.join(self.output_dir, "test.tiff")
        mock_fitz.open.assert_called_with(dummy_pdf_path)
        # cropの戻り値のsaveが呼ばれたことを確認
        mock_img.crop.return_value.save.assert_called_once_with(expected_tiff_path, format='TIFF', compression='tiff_lzw')

    @patch('pipeline.convert.fitz')
    @patch('pipeline.convert.Image')
    def test_header_removal_height(self, mock_image, mock_fitz):
        """変換後の画像の高さが仕様通りか(モックを使用)"""
        # --- モックの設定 ---
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_pix = MagicMock()
        mock_pix.width, mock_pix.height, mock_pix.samples = 2480, 3508, b''
        mock_page.get_pixmap.return_value = mock_pix
        mock_doc.__getitem__.return_value = mock_page # doc[0] をモック
        mock_fitz.open.return_value = mock_doc

        mock_img = MagicMock()
        mock_img.width, mock_img.height = 2480, 3508
        mock_image.frombytes.return_value = mock_img

        # --- 準備 ---
        dummy_pdf_path = os.path.join(self.input_dir, "test.pdf")
        with open(dummy_pdf_path, "w") as f: f.write("dummy")

        # --- 実行 ---
        converter = PDFConverter(self.input_dir, self.output_dir, dpi=300, header_points=79)
        converter.run()

        # --- 検証 ---
        expected_header_pixels = int(79 * 300 / 72)
        mock_img.crop.assert_called_once_with((0, expected_header_pixels, 2480, 3508))

    # @unittest.skip("Not implemented yet")
    def test_empty_directory(self):
        """入力ディレクトリが空の場合にエラーなく終了するか"""
        converter = PDFConverter(self.input_dir, self.output_dir)
        try:
            converter.run()
        except Exception as e:
            self.fail(f"Should not raise an exception on empty dir, but raised {e}")

    # @unittest.skip("Not implemented yet")
    def test_non_pdf_file_ignored(self):
        """PDF以外のファイルが無視されるか"""
        # 準備: .txtファイルのみを作成し、.pdfは作成しない
        dummy_txt_path = os.path.join(self.input_dir, "test.txt")
        with open(dummy_txt_path, "w") as f:
            f.write("some text")

        # 実行
        converter = PDFConverter(self.input_dir, self.output_dir)
        converter.run()

        # 検証: 出力ディレクトリが空のままであることを確認
        output_files = os.listdir(self.output_dir)
        self.assertEqual(len(output_files), 0)

if __name__ == '__main__':
    unittest.main()
