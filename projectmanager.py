# project_manager.py
import os
import sys
import subprocess
from PyQt5.QtWidgets import QInputDialog, QMessageBox, QFileDialog

class ProjectManager:
    def __init__(self):
        self.project_dir = None
        self.current_file_path = None

    def create_new_project(self):
        try:
            project_name, ok = QInputDialog.getText(None, 'New Project', 'Enter project name:')
            if ok and project_name:
                self.project_dir = os.path.join(os.getcwd(), project_name)
                os.makedirs(self.project_dir, exist_ok=True)
                print(f"Created project directory: {self.project_dir}")

                main_file_path = os.path.join(self.project_dir, 'main.py')
                with open(main_file_path, 'w') as file:
                    file.write('')
                print(f"Created main.py file: {main_file_path}")

                venv_dir = os.path.join(self.project_dir, 'venv')
                subprocess.run([sys.executable, '-m', 'venv', venv_dir], check=True)
                print(f"Created virtual environment: {venv_dir}")

        except Exception as e:
            QMessageBox.critical(None, 'Error', f'An error occurred: {str(e)}')

    def open_project(self):
        project_dir = QFileDialog.getExistingDirectory(None, 'Open Project', os.getcwd())
        if project_dir:
            self.project_dir = project_dir
            project_name = os.path.basename(project_dir)
            return project_name

    def create_new_file(self):
        if self.project_dir:
            file_name, ok = QInputDialog.getText(None, 'New File', 'Enter file name (without extension):')
            if ok and file_name:
                file_path = os.path.join(self.project_dir, f'{file_name}.py')
                with open(file_path, 'w') as file:
                    file.write('')
                print(f"Created new file: {file_path}")
                self.current_file_path = file_path
        else:
            QMessageBox.warning(None, 'Warning', 'No project created yet. Please create a new project first.')

    def open_file(self):
        if self.project_dir:
            file_path, _ = QFileDialog.getOpenFileName(None, 'Open File', self.project_dir, 'Python Files (*.py)')
            if file_path:
                with open(file_path, 'r') as file:
                    file_content = file.read()
                self.current_file_path = file_path
                return file_content
        else:
            QMessageBox.warning(None, 'Warning', 'No project opened. Please open a project first.')

    def write_to_file(self, content):
        if self.current_file_path:
            with open(self.current_file_path, 'w') as file:
                file.write(content)
            print(f"Updated file: {self.current_file_path}")