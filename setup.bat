@echo off
chcp 65001 >nul
echo.
echo 🎓 Setting up Athena for Windows...
echo ==================================================
echo.

:: Create directories
echo 📁 Creating directory structure...
mkdir llm_wrappers 2>nul
mkdir utils 2>nul
mkdir frontend\src 2>nul
mkdir models\mistral-7b 2>nul
mkdir .cache 2>nul
mkdir data\CAD_CAM\2D_Transformations 2>nul
mkdir data\CAD_CAM\CNC_Programming 2>nul

:: Install Python dependencies
echo 🐍 Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ❌ Failed to install Python dependencies
    pause
    exit /b 1
)

:: Setup frontend
echo 📦 Setting up frontend dependencies...
cd frontend
call npm install
if %errorlevel% neq 0 (
    echo ❌ Failed to install frontend dependencies
    pause
    exit /b 1
)
cd ..

echo.
echo ✅ Setup complete!
echo.
echo 🚀 Next steps:
echo    1. Add your CAD/CAM PDFs to the data\ directory
echo    2. Choose a local model option:
echo.
echo    Option A - Using Ollama ^(recommended^):
echo        Visit https://ollama.com and download the Windows installer
echo        Then run: ollama pull mistral
echo.
echo    Option B - Manual download:
echo        Download mistral-7b.ggml.q4_0.bin and place in models\mistral-7b\
echo.
echo    3. Run the system:
echo        python main.py                    # CLI version
echo        python flask_api_server.py        # API server  
echo        cd frontend ^&^& npm start        # Web UI
echo.
echo    4. For cloud AI, set your Gemini API key:
echo        set GOOGLE_API_KEY=your_key_here
echo.
echo 🔧 Configuration file: config.json
echo.
pause