import sys
import os
import time
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit, QLineEdit, QLabel, QMessageBox, QProgressBar, QTabWidget, QGraphicsEllipseItem, QGraphicsTextItem, QDesktopWidget, QSizePolicy, QDialog, QGraphicsView, QGraphicsScene
from PyQt5.QtGui import QColor, QBrush, QPainter
from PyQt5.QtCore import Qt
from PyQt5.Qsci import QsciScintilla, QsciLexerPython
from PyQt5.QtCore import QProcess, QProcessEnvironment
import traceback
import subprocess
import google.generativeai as genai
from highlighter import PythonHighlighter
from projectmanager import ProjectManager
import re
import configparser

def load_api_key(f='api_key.txt'):
    config = configparser.ConfigParser()
    config.read(f)
    return config.get('GOOGLE', 'api_key')

def extract_code(text):
    code_block = re.search(r'```python\n(.*?)\n```', text, re.DOTALL)
    if code_block:
        return code_block.group(1)
    return ''

class TaskNode:
    def __init__(self, task, parent=None):
        self.task = task
        self.parent = parent
        self.children = []

    def add_child(self, task_node):
        self.children.append(task_node)

    def get_task_filename(self):
        if self.parent is None:
            return self.task['prompt']
        else:
            parent_filename = self.parent.get_task_filename()
            task_index = self.parent.children.index(self) + 1
            return f"{parent_filename}-{task_index}"
        

class SubtaskWindow(QWidget):
    def __init__(self, subtask, project_manager, parent_window, main_task_filename, subtask_number, total_subtasks):
        super().__init__()
        self.subtask = subtask
        self.project_manager = project_manager
        self.parent_window = parent_window
        self.main_task_filename = main_task_filename
        self.subtask_number = subtask_number
        self.total_subtasks = total_subtasks

        with open('stylesheet.css', 'r') as f:
            self.setStyleSheet(f.read())

        self.setWindowTitle(f"Subtask {self.subtask_number}: {subtask[:30]}...")
        
        layout = QVBoxLayout()
        
        subtask_text_edit = QTextEdit()
        subtask_text_edit.setPlainText(subtask)
        layout.addWidget(subtask_text_edit)

        submit_button = QPushButton("Submit")
        submit_button.clicked.connect(lambda: self.submit_subtask(subtask_text_edit.toPlainText()))
        layout.addWidget(submit_button)

        code_label = QLabel("Code:")
        layout.addWidget(code_label)
        
        self.code_display = QsciScintilla()
        self.code_display.setReadOnly(True)
        lexer = QsciLexerPython()
        self.code_display.setLexer(lexer)
        layout.addWidget(self.code_display)
        
        self.execute_button = QPushButton("Execute")
        self.execute_button.clicked.connect(self.execute_subtask)
        layout.addWidget(self.execute_button)

        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)
        layout.addWidget(self.output_display)

        self.approve_button = QPushButton("Approve")
        self.approve_button.clicked.connect(self.approve_subtask)
        self.approve_button.setEnabled(False)
        layout.addWidget(self.approve_button)

        self.include_buttons_layout = QHBoxLayout()
        layout.addLayout(self.include_buttons_layout)

        self.setLayout(layout)

        self.setMinimumSize(1200, 1024)
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.activateWindow()

    def submit_subtask(self, subtask):
        try:
            response = self.parent_window.model.generate_content(subtask)
            generated_code = extract_code(response.text)
            self.code_display.setText(generated_code)
            self.save_subtask()
        except Exception as e:
            print(traceback.print_exc())
            QMessageBox.critical(self, 'Error', f'An error occurred while submitting subtask: {str(e)}')

    def save_subtask(self):
        code = self.code_display.text()
        if code.strip():
            try:
                main_filename = os.path.splitext(self.main_task_filename)[0]
                new_filename = f"{main_filename}-{self.subtask_number}.py"
                file_path = os.path.join(self.project_manager.project_dir, new_filename)
                with open(file_path, 'w') as file:
                    file.write(code)
                QMessageBox.information(self, 'Success', f'Subtask saved successfully as {new_filename}')
            except Exception as e:
                print(traceback.print_exc())
                QMessageBox.critical(self, 'Error', f'An error occurred while saving subtask: {str(e)}')
        else:
            QMessageBox.warning(self, 'Warning', 'No code to save for this subtask.')

    def execute_subtask(self):
        try:
            code = self.code_display.text()
            if code.strip():
                main_filename = os.path.splitext(self.main_task_filename)[0]
                filename = f"{main_filename}-{self.subtask_number}.py"
                file_path = os.path.join(self.project_manager.project_dir, filename)
                self.run_code(file_path)
            else:
                QMessageBox.warning(self, 'Warning', 'No code to execute for this subtask.')
        except Exception as e:
            print(traceback.print_exc())
            QMessageBox.critical(self, 'Error', f'An error occurred while executing subtask: {str(e)}')

    def run_code(self, file_path):
        try:
            if file_path:
                venv_dir = os.path.join(self.project_manager.project_dir, 'venv')
                venv_python = os.path.join(venv_dir, 'Scripts', 'python') if sys.platform == 'win32' else os.path.join(venv_dir, 'bin', 'python')

                self.process = QProcess(self)
                self.process.setProcessChannelMode(QProcess.MergedChannels)
                self.process.readyReadStandardOutput.connect(self.handle_stdout)
                self.process.finished.connect(self.process_finished)

                env = QProcessEnvironment.systemEnvironment()
                env.insert("PYTHONUNBUFFERED", "1")
                self.process.setProcessEnvironment(env)

                self.process.start(venv_python, [file_path])
            else:
                QMessageBox.warning(self, 'Warning', 'No file opened. Please open a file first.')
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Exception in run_code: {e}')

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        self.output_display.append(data)

    def process_finished(self):
        self.output_display.append("Process finished.")
        self.approve_button.setEnabled(True)

    def approve_subtask(self):
        self.parent_window.subtask_approved(self.subtask_number)
        self.close()

    def include_subtask(self, subtask_number):
        approved_subtask_file = f"{os.path.splitext(self.main_task_filename)[0]}-{subtask_number}.py"
        approved_subtask_path = os.path.join(self.project_manager.project_dir, approved_subtask_file)
        
        with open(approved_subtask_path, 'r') as f:
            approved_code = f.read()
        
        current_code = self.code_display.text()
        updated_code = f"""# Including code from subtask #{subtask_number}
# Begin included code
{approved_code}
# End included code

# Original code for this subtask
{current_code}"""
        
        self.code_display.setText(updated_code)
        QMessageBox.information(self, 'Subtask Included', f'Code from subtask #{subtask_number} has been included in this subtask.')


class CodeGenApp(QWidget):
    def __init__(self):
        super().__init__()
        with open('stylesheet.css', 'r') as f:
            self.setStyleSheet(f.read())

        self.task_tree = TaskNode({'prompt': 'Root', 'status': 'in_progress'})
        self.current_node = self.task_tree

        self.task_tree_view = TaskTreeView()

        genai.configure(api_key=load_api_key())
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.setWindowTitle('Code Generation App')

        layout = QVBoxLayout()

        self.tab_widget = QTabWidget()
        self.code_gen_tab = QWidget()
        self.task_tree_tab = QWidget()

        self.new_project_tab = NewProjectTab(self)
        self.tab_widget.addTab(self.code_gen_tab, 'Code Generation')
        self.tab_widget.addTab(self.task_tree_tab, 'Task Tree')
        self.tab_widget.addTab(self.new_project_tab, 'New Project')

        code_gen_layout = QVBoxLayout()
        task_tree_layout = QVBoxLayout()

        self.current_project_label = QLabel('Current Project: None')

        self.prompt_label = QLabel('Enter Prompt:')
        self.prompt_input = QTextEdit()
        self.submit_button = QPushButton('Submit')
        self.submit_button.clicked.connect(self.handleSubmit)

        self.complete_output_label = QLabel('Complete Output:')
        self.complete_output_display = QTextEdit()
        self.complete_output_display.setReadOnly(True)

        self.generated_code_label = QLabel('Generated Code:')
        self.generated_code_display = QsciScintilla()
        self.generated_code_display.setReadOnly(True)
        self.lexer = QsciLexerPython()
        self.generated_code_display.setLexer(self.lexer)

        self.output_label = QLabel('Execution Output:')
        self.output_display = QTextEdit()
        self.output_display.setReadOnly(True)

        self.approve_button = QPushButton('Approve')
        self.refactor_button = QPushButton('Refactor')
        self.breakdown_button = QPushButton('Further Breakdown')
        self.delete_button = QPushButton('Delete')

        self.approve_button.clicked.connect(self.handleApprove)
        self.refactor_button.clicked.connect(self.handleRefactor)
        self.breakdown_button.clicked.connect(self.handleBreakdown)
        self.delete_button.clicked.connect(self.handleDelete)

        self.execute_button = QPushButton('Execute')
        self.execute_button.clicked.connect(self.handle_execute)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        self.status_label = QLabel()

        self.pm = ProjectManager()

        self.create_project_button = QPushButton('Create New Project')
        self.create_project_button.clicked.connect(self.create_new_project)

        self.open_project_button = QPushButton('Open Project')
        self.open_project_button.clicked.connect(self.open_project)

        self.create_file_button = QPushButton('Create New File')
        self.create_file_button.clicked.connect(self.create_new_file)
        self.create_file_button.setEnabled(False)

        self.open_file_button = QPushButton('Open File')
        self.open_file_button.clicked.connect(self.open_file)
        self.open_file_button.setEnabled(False)

        project_buttons_layout = QHBoxLayout()
        project_buttons_layout.addWidget(self.open_project_button)
        project_buttons_layout.addWidget(self.create_project_button)

        file_buttons_layout = QHBoxLayout()
        file_buttons_layout.addWidget(self.open_file_button)
        file_buttons_layout.addWidget(self.create_file_button)

        code_gen_layout.addWidget(self.current_project_label)
        code_gen_layout.addLayout(project_buttons_layout)
        code_gen_layout.addLayout(file_buttons_layout)
        code_gen_layout.addWidget(self.prompt_label)
        code_gen_layout.addWidget(self.prompt_input)
        code_gen_layout.addWidget(self.submit_button)
        code_gen_layout.addWidget(self.complete_output_label)
        code_gen_layout.addWidget(self.complete_output_display)
        code_gen_layout.addWidget(self.generated_code_label)
        code_gen_layout.addWidget(self.generated_code_display)
        code_gen_layout.addWidget(self.output_label)
        code_gen_layout.addWidget(self.output_display)
        code_gen_layout.addWidget(self.execute_button)
        code_gen_layout.addWidget(self.approve_button)
        code_gen_layout.addWidget(self.refactor_button)
        code_gen_layout.addWidget(self.breakdown_button)
        code_gen_layout.addWidget(self.delete_button)
        code_gen_layout.addWidget(self.progress_bar)
        code_gen_layout.addWidget(self.status_label)

        task_tree_layout.addWidget(self.task_tree_view)

        self.code_gen_tab.setLayout(code_gen_layout)
        self.task_tree_tab.setLayout(task_tree_layout)

        layout.addWidget(self.tab_widget)
        self.setLayout(layout)
        self.setWindowSize()

        self.subtask_windows = []
        self.approved_subtasks = set()

    def setWindowSize(self):
        self.setMinimumSize(1024, 768)  # Set minimum width and height
        screen = QDesktopWidget().screenGeometry()
        w = int(screen.width() / 2)
        h = int(screen.height() * 3 / 4)
        print(f'Setting window size: width={w}, height={h}')
        self.resize(w,h)
        self.centerOnScreen() # Center the window on the screen
        
    def centerOnScreen(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def create_new_project(self):
        self.pm.create_new_project()
        self.create_file_button.setEnabled(True)
        self.open_file_button.setEnabled(True)

    def open_project(self):
        project_name = self.pm.open_project()
        if project_name:
            self.current_project_label.setText(f'Current Project: {project_name}')
            self.create_file_button.setEnabled(True)
            self.open_file_button.setEnabled(True)

    def create_new_file(self):
        self.pm.create_new_file()
        self.submit_button.setEnabled(True)

    def open_file(self):
        file_content = self.pm.open_file()
        if file_content:
            self.generated_code_display.setText(file_content)
            self.submit_button.setEnabled(True)

    def handleSubmit(self):
        prompt = self.prompt_input.toPlainText()
        analysis_prompt = f"""Analyze the following prompt and determine if it's a simple task that can be completed directly, or a more complex task that should be broken down into subtasks.

If it's a simple task (e.g., write a Python program to print the Fibonacci sequence), begin with "SIMPLE:", then complete the task and generate the code.

If it's a complex task, begin your response with "SUBTASKS:", then provide a numbered list of subtasks that would be necessary to complete it. Each subtask should be written as an AI prompt that can be used to generate code for that specific part of the task. Do not generate code for the subtasks at this stage.

When creating the subtask prompts, the following is vital:
- Provide all necessary context or constraints to ensure the generated code snippets will be compatible.
- Each prompt should focus on a specific part of the overall task.
- Use clear and concise language to describe the desired functionality of each subtask.
- Do not include any code in the subtask prompts.

**Prompt:** {prompt}"""

        try:
            response = self.model.generate_content(analysis_prompt)
            analysis_result = response.text.strip()
            self.complete_output_display.setPlainText(analysis_result)

            if "SUBTASKS:" in analysis_result:
                start_index = analysis_result.find('1.')
                analysis = analysis_result[start_index:]

                subtasks = self.split_tasks(analysis)

                main_task_filename = f"main_task_{int(time.time())}.py"
                self.pm.current_file_path = os.path.join(self.pm.project_dir, main_task_filename)

                self.progress_bar.setMaximum(len(subtasks))
                self.progress_bar.setValue(0)
                self.progress_bar.setVisible(True)

                for i, sub in enumerate(subtasks, start=1):
                    subtask_prompt = f"This is subtask {i} of {len(subtasks)} for the following overall task: ---\n\n{prompt}\n\nThe subtasks for this task are:\n{analysis}\n\nKeep the other subtasks in mind when writing the code for this subtask, but only complete subtask #{i}\n"
                    subtask_window = SubtaskWindow(subtask_prompt, self.pm, self, main_task_filename, i, len(subtasks))
                    subtask_window.move(20*i, 20*i)  # Offset each window
                    subtask_window.show()
                    self.subtask_windows.append(subtask_window)

                self.status_label.setText(f'Task broken down into {len(subtasks)} subtasks.')
            else:
                # Simple task, proceed with normal generation
                self.progress_bar.setVisible(True)
                self.progress_bar.setValue(0)
                self.status_label.setText('Generating code...')
                QApplication.processEvents()

                try:
                    generated_code = extract_code(response.text)
                    self.progress_bar.setValue(30)
                    QApplication.processEvents()

                    self.status_label.setText('Creating virtual environment...')
                    venv_path = self.create_venv()
                    self.progress_bar.setValue(50)
                    QApplication.processEvents()

                    self.status_label.setText('Installing libraries...')
                    libraries = self.parse_libraries(generated_code)
                    self.install_libraries(venv_path, libraries)
                    self.progress_bar.setValue(70)
                    QApplication.processEvents()

                    self.generated_code_display.setText(generated_code)
                    self.status_label.setText('Code generation completed.')
                    QApplication.processEvents()

                    if self.pm.current_file_path:
                        self.pm.write_to_file(self.pm.current_file_path, generated_code)

                    task = {
                        'prompt': prompt,
                        'code': generated_code,
                        'output': '',
                        'status': 'in_progress'
                    }
                    task_node = TaskNode(task, parent=self.current_node)
                    self.current_node.add_child(task_node)
                    self.current_node = task_node

                    filename = task_node.get_task_filename()
                    self.pm.write_to_file(filename, generated_code)

                    self.visualize_tasks()
                except Exception as e:
                    print(traceback.print_exc())
                    QMessageBox.critical(self, 'Error', f'An error occurred: {str(e)}')
                finally:
                    self.progress_bar.setVisible(False)
                    self.status_label.setText('')

        except Exception as e:
            print(traceback.print_exc())
            QMessageBox.critical(self, 'Error', f'An error occurred while analyzing complexity: {str(e)}')
        finally:
            self.progress_bar.setVisible(False)
            self.status_label.setText('')

    def split_tasks(self, text):
        lines = text.split("\n")
        tasks = []
        curr_task = ""

        for line in lines:
            line = line.strip()
            print(f'LINE={line}')
            match = re.match(r"^\d+\.", line)
            if match and len(curr_task) > 0:
                tasks.append(curr_task)
                curr_task = line
            else:
                curr_task += line

        tasks.append(curr_task)
        return tasks

    def generate_code(self, prompt):
        response = self.model.generate_content(prompt)
        return response.text

    def handle_execute(self):
        filename = self.current_node.get_task_filename()
        file_path = os.path.join(self.pm.project_dir, filename)
        if os.path.exists(file_path):
            self.run_code(file_path)
        else:
            QMessageBox.warning(self, 'Warning', 'No file found. Please submit the task first.')

    def handleApprove(self):
        if self.current_node.task['status'] == 'complete':
            QMessageBox.information(self, 'Success', 'Task already completed.')
        else:
            self.current_node.task['status'] = 'complete'
            self.visualize_tasks()
            QMessageBox.information(self, 'Success', 'Task approved and marked as complete.')

    def handleRefactor(self):
        if self.current_node.task['status'] == 'complete':
            QMessageBox.warning(self, 'Warning', 'Cannot refactor a completed task.')
            return

        prompt = f"Please refactor the following code:\n\n{self.current_node.task['code']}"
        try:
            response = self.model.generate_content(prompt)
            refactored_code = response.text.strip()
            self.current_node.task['code'] = refactored_code
            self.visualize_tasks()
            QMessageBox.information(self, 'Success', 'Task refactored successfully.')
        except Exception as e:
            print(traceback.print_exc())
            QMessageBox.critical(self, 'Error', f'An error occurred while refactoring: {str(e)}')

    def handleBreakdown(self):
        if self.current_node.task['status'] == 'complete':
            QMessageBox.warning(self, 'Warning', 'Cannot break down a completed task.')
            return

        prompt = f"Please break down the following task into smaller subtasks:\n\n{self.current_node.task['prompt']}"
        try:
            response = self.model.generate_content(prompt)
            subtasks = response.text.strip().split('\n')
            for subtask in subtasks:
                subtask_window = SubtaskWindow(subtask, self.pm, self, self.pm.current_file_path, len(self.subtask_windows) + 1, len(subtasks))
                subtask_window.show()
                self.subtask_windows.append(subtask_window)
        except Exception as e:
            print(traceback.print_exc())
            QMessageBox.critical(self, 'Error', f'An error occurred while breaking down the task: {str(e)}')

    def handleDelete(self):
        if self.current_node == self.task_tree:
            QMessageBox.warning(self, 'Warning', 'Cannot delete the root task.')
        else:
            parent_node = self.current_node.parent
            parent_node.children.remove(self.current_node)
            self.current_node = parent_node
            self.visualize_tasks()
            QMessageBox.information(self, 'Success', 'Task deleted.')
    
    def generate_summary(self, task):
        prompt = f"Please provide a brief one-sentence summary of the following task:\n\n{task['prompt']}"
        try:
            response = self.model.generate_content(prompt)
            print(f"generate_summary response: {response}")
            return response.text
        except Exception as e:
            print(traceback.print_exc())
            QMessageBox.critical(self, 'Error', f'An error occurred while generating summary: {str(e)}')
            return 'Summary generation failed'

    def visualize_tasks(self):
        self.task_tree_view.visualize_tasks(self.task_tree, self)

    def create_venv(self):
        try:
            venv_path = os.path.join(os.getcwd(), 'venv')
            print(f"create_venv: {venv_path}")
            subprocess.run([sys.executable, '-m', 'venv', venv_path])
            return venv_path
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Exception in create_venv: {e}')

    def install_libraries(self, venv_path, libraries):
        pip_path = os.path.join(venv_path, 'Scripts', 'pip')
        for lib in libraries:
            print(f"install_libraries: {pip_path} install {lib}")
            subprocess.run([pip_path, 'install', lib])

    def run_code(self, file_path):
        try:
            if file_path:
                venv_dir = os.path.join(self.pm.project_dir, 'venv')
                venv_python = os.path.join(venv_dir, 'Scripts', 'python') if sys.platform == 'win32' else os.path.join(venv_dir, 'bin', 'python')

                self.process = QProcess(self)
                self.process.setProcessChannelMode(QProcess.MergedChannels)
                self.process.readyReadStandardOutput.connect(self.handle_stdout)
                self.process.finished.connect(self.process_finished)

                env = QProcessEnvironment.systemEnvironment()
                env.insert("PYTHONUNBUFFERED", "1")
                self.process.setProcessEnvironment(env)

                self.process.start(venv_python, [file_path])
            else:
                QMessageBox.warning(self, 'Warning', 'No file opened. Please open a file first.')
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Exception in run_code: {e}')

    def parse_libraries(self, code):
        import_lines = [line for line in code.splitlines() if line.startswith('import') or line.startswith('from')]
        libraries = []
        for line in import_lines:
            parts = line.split()
            if 'import' in parts:
                lib = parts[parts.index('import') + 1]
                libraries.append(lib.split('.')[0])
            if 'from' in parts:
                lib = parts[parts.index('from') + 1]
                libraries.append(lib.split('.')[0])
        print(f"parse_libraries: {libraries}")
        return libraries

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        self.output_display.append(data)

    def process_finished(self):
        self.output_display.append("Process finished.")

    def send_input(self):
        try:
            input_text = self.input_line_edit.text()
            self.process.write(f"{input_text}\n".encode())
            self.input_line_edit.clear()
        except Exception as e:
            QMessageBox.information(self, 'Error', f'Exception in send_input: {e}')

    def subtask_approved(self, subtask_number):
        self.approved_subtasks.add(subtask_number)
        self.progress_bar.setValue(len(self.approved_subtasks))
        
        for window in self.subtask_windows:
            if window.subtask_number != subtask_number:
                include_button = QPushButton(f"Include Subtask #{subtask_number}")
                include_button.clicked.connect(lambda checked, n=subtask_number, w=window: w.include_subtask(n))
                window.include_buttons_layout.addWidget(include_button)

        if len(self.approved_subtasks) == len(self.subtask_windows):
            self.all_subtasks_completed()
        
    def all_subtasks_completed(self):
        QMessageBox.information(self, 'Success', 'All subtasks have been completed and approved!')
        # Combine all subtasks into the final result, maybe?


class NewProjectTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        self.code_input = QTextEdit()
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.code_input.sizePolicy().hasHeightForWidth())
        self.code_input.setSizePolicy(sizePolicy)
        PythonHighlighter(self.code_input.document())
        self.code_input.show()
        self.code_input.textChanged.connect(self.update_run_button_state)

        self.output_text_edit = QTextEdit()
        self.output_text_edit.setReadOnly(True)

        self.input_line_edit = QLineEdit()
        self.send_input_button = QPushButton('Send Input')
        self.send_input_button.clicked.connect(self.send_input)

        self.current_project_label = QLabel('Current Project: None')

        self.run_button = QPushButton('Run Code')
        self.run_button.clicked.connect(self.run_code)

        self.run_button.setEnabled(False)  # Initially disabled

        self.create_project_button = QPushButton('Create New Project')
        self.create_project_button.clicked.connect(self.create_new_project)

        self.open_project_button = QPushButton('Open Project')
        self.open_project_button.clicked.connect(self.open_project)

        self.create_file_button = QPushButton('Create New File')
        self.create_file_button.clicked.connect(self.create_new_file)
        self.create_file_button.setEnabled(False)

        self.open_file_button = QPushButton('Open File')
        self.open_file_button.clicked.connect(self.open_file)
        self.open_file_button.setEnabled(False)

        project_buttons_layout = QHBoxLayout()
        project_buttons_layout.addWidget(self.create_project_button)
        project_buttons_layout.addWidget(self.open_project_button)

        file_buttons_layout = QHBoxLayout()
        file_buttons_layout.addWidget(self.create_file_button)
        file_buttons_layout.addWidget(self.open_file_button)

        code_input_layout = QVBoxLayout()
        code_input_layout.addWidget(self.code_input)
        code_input_layout.addWidget(self.run_button)

        layout.addWidget(self.current_project_label)
        layout.addLayout(project_buttons_layout)
        layout.addLayout(file_buttons_layout)
        layout.addWidget(QLabel('Code Input:'))
        layout.addLayout(code_input_layout)
        layout.addWidget(QLabel('Output:'))
        layout.addWidget(self.output_text_edit)
        layout.addWidget(QLabel('Input:'))
        layout.addWidget(self.input_line_edit)
        layout.addWidget(self.send_input_button)

        self.setLayout(layout)

        self.pm = ProjectManager()

    def update_run_button_state(self):
        code = self.code_input.toPlainText().strip()
        self.run_button.setEnabled(bool(code))

    def send_input(self):
        input_text = self.input_line_edit.text()
        self.process.write(f"{input_text}\n".encode())
        self.input_line_edit.clear()

    def create_new_project(self):
        self.pm.create_new_project()
        self.create_file_button.setEnabled(True)
        self.open_file_button.setEnabled(True)

    def open_project(self):
        project_name = self.pm.open_project()
        if project_name:
            self.current_project_label.setText(f'Current Project: {project_name}')
            self.create_file_button.setEnabled(True)
            self.open_file_button.setEnabled(True)

    def create_new_file(self):
        self.pm.create_new_file()
        self.run_button.setEnabled(True)

    def open_file(self):
        file_content = self.pm.open_file()
        if file_content:
            self.code_input.setPlainText(file_content)
            self.run_button.setEnabled(True)

    def run_code(self):
        if self.pm.current_file_path:
            with open(self.pm.current_file_path, 'w') as file:
                file.write(self.code_input.toPlainText())
            print(f"Updated file: {self.pm.current_file_path}")

            venv_dir = os.path.join(self.pm.project_dir, 'venv')
            venv_python = os.path.join(venv_dir, 'Scripts', 'python') if sys.platform == 'win32' else os.path.join(venv_dir, 'bin', 'python')

            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.handle_stdout)
            self.process.finished.connect(self.process_finished)

            env = QProcessEnvironment.systemEnvironment()
            env.insert("PYTHONUNBUFFERED", "1")
            self.process.setProcessEnvironment(env)

            self.process.start(venv_python, [self.pm.current_file_path])
        else:
            QMessageBox.warning(self, 'Warning', 'No file opened. Please open a file first.')

    def handle_stdout(self):
        data = self.process.readAllStandardOutput().data().decode()
        self.output_text_edit.append(data)

    def process_finished(self):
        self.output_text_edit.append("Process finished.")

class TaskTreeView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            zoom_factor = 1.25
            if event.angleDelta().y() < 0:
                zoom_factor = 1 / zoom_factor
            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def visualize_tasks(self, task_tree, code_gen_app):
        self.scene.clear()
        self._visualize_task_node(task_tree, 0, 0, code_gen_app)
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def _visualize_task_node(self, task_node, x, y, code_gen_app, level=0):
        color = QColor(Qt.red)
        if task_node.task['status'] == 'complete':
            color = QColor(Qt.green)
        elif task_node.task['status'] == 'in_progress':
            color = QColor(Qt.blue)

        bubble = QGraphicsEllipseItem(x, y, 120, 80)
        bubble.setBrush(QBrush(color))
        self.scene.addItem(bubble)

        summary = code_gen_app.generate_summary(task_node.task)
        text = QGraphicsTextItem(summary[:50])
        text.setPos(x + 10, y + 30)
        self.scene.addItem(text)

        for i, child_node in enumerate(task_node.children):
            child_x = x + 150
            child_y = y + i * 100
            self._visualize_task_node(child_node, child_x, child_y, code_gen_app, level + 1)
            self.scene.addLine(x + 120, y + 40, child_x, child_y + 40)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = CodeGenApp()
    ex.show()
    sys.exit(app.exec_())