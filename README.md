# MIND-FLOW (Cognitive Productivity Tracker)

MIND-FLOW is a desktop application that acts as your digital sanctuary, tracking your cognitive load and reminding you to take restorative breaks before you burn out.

## 🚀 How to Launch the App

To run the application, simply double-click the **`Launch MIND-FLOW.bat`** file located in this folder.

Alternatively, you can run it from PowerShell:
```powershell
.\.venv\Scripts\python.exe app.py
```

## 🛠️ How to Develop & Build the UI

The user interface is a React/Vite application located in the `Cognitive Productivity Tracker UI` folder. 
If you make changes to the React code, you **must build it** so the Python backend can serve the new files.

1. Open PowerShell and navigate to the UI folder:
   ```powershell
   cd "Cognitive Productivity Tracker UI"
   ```
2. Build the project:
   ```powershell
   npm run build
   ```
   *(The `postbuild` script will automatically copy the generated files to the `static` and `templates` folders where the Flask backend expects them).*

To run a live development server for the UI only:
```powershell
npm run dev
```
