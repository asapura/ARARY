# Makefile for ARARY Project

.PHONY: convert

# --- Variable Definitions ---
PYTHON = python3
INPUT_DIR_RAW = data/raw/saitama
OUTPUT_DIR_TIFF = data/tiff/saitama

# --- Targets ---

convert:
	@echo "Converting PDF files to TIFF..."
	@mkdir -p $(OUTPUT_DIR_TIFF)
	$(PYTHON) -c "from pipeline.convert import PDFConverter; converter = PDFConverter('$(INPUT_DIR_RAW)', '$(OUTPUT_DIR_TIFF)'); converter.run()"
	@echo "Conversion complete."
