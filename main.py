import sys
import os
import json
import random
import psutil
import time
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QLineEdit, QListWidget, 
                            QFileDialog, QMessageBox, QInputDialog, QSystemTrayIcon, 
                            QMenu, QAction)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QEvent
from PyQt5.QtGui import QIcon, QPixmap, QImage
import os.path
from pathlib import Path


class Word:
    def __init__(self, english="", french=""):
        self.english = english
        self.french = french

class Executable:
    def __init__(self, name="", path=""):
        self.name = name
        self.path = path
        self.filename = os.path.basename(path)

class ProcessWatcher(QObject):
    executableLaunched = pyqtSignal(Executable)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.executables = []
        self.running = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_processes)
        self.monitored_procs = set()
        self.authorized_executables = {}
        self.authorized_pids = {}

    def set_executables(self, execs):
        self.executables = execs
        self.monitored_procs = set()

    def start(self):
        self.monitored_procs = set()
        self.running = True
        self.timer.start(1000)

    def stop(self):
        self.running = False
        self.timer.stop()

    def authorize_executable(self, path, pid=None):
        self.authorized_executables[path.lower()] = True
        print(f"Exécutable autorisé: {path}")
        if pid:
            if path.lower() not in self.authorized_pids:
                self.authorized_pids[path.lower()] = set()
            self.authorized_pids[path.lower()].add(pid)

    def check_processes(self):
        for proc in psutil.process_iter(['pid', 'name', 'exe']):
            try:
                if proc.pid in self.monitored_procs:
                    continue
                for exec in self.executables:
                    proc_name = proc.info['name'].lower()
                    exec_name = os.path.basename(exec.filename).lower()
                    exec_path = exec.path.lower()
                    if exec_path in self.authorized_executables:
                        continue
                    if exec_name in proc_name:
                        self.monitored_procs.add(proc.pid)
                        proc.kill()
                        self.executableLaunched.emit(exec)
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

class EnglishLearningApp(QWidget):
    def __init__(self):
        super().__init__()
        self.words = []
        self.executables = []
        self.json_file_path = "words.json"
        self.executables_file_path = "executables.json"
        self.tray_icon = None
        self.executables_list = None
        self.process_watcher = None
        self.translation_dialog = None
        self.word_label = None
        self.translation_input = None
        self.submit_button = None
        self.cancel_button = None
        self.current_word = None
        self.current_executable = None
        self.attempts = 0
        self.max_attempts = 3
        self.failed_attempts = 0
        
        self.load_words()
        self.load_executables()
        self.init_ui()
        
        self.process_watcher = ProcessWatcher()
        self.process_watcher.executableLaunched.connect(self.on_executable_launched)
        self.process_watcher.set_executables(self.executables)
        self.process_watcher.start()
    
    def init_ui(self):
        self.setWindowTitle("Application d'apprentissage d'anglais")
        self.setMinimumSize(600, 400)
        
        main_layout = QVBoxLayout()
        
        title_label = QLabel("<h1>Application d'apprentissage d'anglais</h1>")
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        info_label = QLabel(
            "Sélectionnez les exécutables que vous souhaitez surveiller. "
            "Quand vous lancerez un de ces programmes, un test de traduction vous sera proposé avant."
        )
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        self.executables_list = QListWidget()
        main_layout.addWidget(self.executables_list)
        
        button_layout = QHBoxLayout()
        add_button = QPushButton("Ajouter un exécutable")
        remove_button = QPushButton("Supprimer l'exécutable sélectionné")
        minimize_button = QPushButton("Minimiser dans la barre des tâches")
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(minimize_button)
        main_layout.addLayout(button_layout)
        
        add_button.clicked.connect(self.add_executable)
        remove_button.clicked.connect(self.remove_executable)
        minimize_button.clicked.connect(self.hide_to_tray)
        
        self.setup_tray_icon()
        self.update_executables_list()
        self.setLayout(main_layout)

    def setup_tray_icon(self):
        icon_path = "./app_icon.png"
        if not os.path.exists(icon_path):
            self.tray_icon = QSystemTrayIcon(QIcon.fromTheme("application-x-executable"), self)
        else:
            self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self)
            
        tray_menu = QMenu()
        show_action = QAction("Afficher", self)
        quit_action = QAction("Quitter", self)
        
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(QApplication.quit)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        self.tray_icon.show()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()

    def load_words(self):
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.words = []
                for item in data:
                    word = Word(item["english"], item["french"])
                    self.words.append(word)
                print(f"Chargement de {len(self.words)} mots réussi.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des mots: {str(e)}")

    def load_executables(self):
        try:
            if not os.path.exists(self.executables_file_path):
                self.executables = []
                return
            with open(self.executables_file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                self.executables = []
                for item in data:
                    exec = Executable(item["name"], item["path"])
                    self.executables.append(exec)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du chargement des exécutables: {str(e)}")

    def save_executables(self):
        try:
            data = []
            for exec in self.executables:
                item = {
                    "name": exec.name,
                    "path": exec.path
                }
                data.append(item)
            with open(self.executables_file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la sauvegarde des exécutables: {str(e)}")

    def update_executables_list(self):
        self.executables_list.clear()
        for exec in self.executables:
            self.executables_list.addItem(f"{exec.name} ({exec.path})")
        if self.process_watcher:
            self.process_watcher.set_executables(self.executables)

    def get_random_word(self):
        if not self.words:
            return Word("error", "erreur")
        return random.choice(self.words)

    def execute_program(self, path):
        try:
            os.startfile(path) if sys.platform == 'win32' else os.system(f'open "{path}"') if sys.platform == 'darwin' else os.system(f'xdg-open "{path}"')
            return True
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du lancement de {path}: {str(e)}")
            return False

    def create_translation_dialog(self, exec):
        self.current_executable = exec
        self.current_word = self.get_random_word()
        self.attempts = 0
        if self.translation_dialog:
            self.translation_dialog.close()
        self.translation_dialog = QWidget(None, Qt.Window | Qt.WindowStaysOnTopHint)
        self.translation_dialog.setWindowTitle("Test de traduction")
        self.translation_dialog.setFixedSize(400, 200)
        
        screen_rect = QApplication.desktop().screenGeometry()
        self.translation_dialog.move(screen_rect.center() - self.translation_dialog.rect().center())
        layout = QVBoxLayout()
        info_label = QLabel(f"Pour lancer {self.current_executable.name}, traduisez ce mot en français:")
        layout.addWidget(info_label)
        self.word_label = QLabel(f"<h2>{self.current_word.english}</h2>")
        self.word_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.word_label)
        self.translation_input = QLineEdit()
        layout.addWidget(self.translation_input)
        attempts_label = QLabel(f"Tentative 1/{self.max_attempts}")
        layout.addWidget(attempts_label)
        button_layout = QHBoxLayout()
        self.submit_button = QPushButton("Valider")
        self.cancel_button = QPushButton("Annuler")
        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        self.submit_button.clicked.connect(lambda: self.check_translation(attempts_label))
        self.cancel_button.clicked.connect(self.translation_dialog.close)
        self.translation_input.returnPressed.connect(self.submit_button.click)
        self.translation_dialog.setLayout(layout)
        self.translation_dialog.show()
        self.translation_input.setFocus()

    def check_translation(self, attempts_label):
        answer = self.translation_input.text().strip().lower()
        correct_answer = self.current_word.french.lower()
        if answer == correct_answer:
            executable_path = self.current_executable.path
            QMessageBox.information(self.translation_dialog, "Bravo!", "Traduction correcte!")
            self.translation_dialog.close()
            QTimer.singleShot(100, lambda: self.execute_program_and_authorize(executable_path))
        else:
            self.attempts += 1
            if self.attempts >= self.max_attempts:
                QMessageBox.critical(self.translation_dialog, "Échec", f"Vous avez échoué 3 fois. La réponse correcte était: {self.current_word.french}")
                self.translation_dialog.close()
                self.failed_attempts += 1
                if self.failed_attempts >= 3:
                    self.shutdown_computer()
                    self.failed_attempts = 0
            else:
                QMessageBox.warning(self.translation_dialog, "Incorrect", "Essayez encore.")
                attempts_label.setText(f"Tentative {self.attempts + 1}/{self.max_attempts}")
                self.translation_input.clear()
                self.translation_input.setFocus()

    def execute_program_and_authorize(self, path):
        try:
            if sys.platform == 'win32':
                os.startfile(path)
                QTimer.singleShot(500, lambda: self.find_and_authorize_process(path))
            else:
                if sys.platform == 'darwin':
                    os.system(f'open "{path}"')
                else:
                    os.system(f'xdg-open "{path}"')
                QTimer.singleShot(500, lambda: self.find_and_authorize_process(path))
            return True
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors du lancement de {path}: {str(e)}")
            return False

    def find_and_authorize_process(self, path):
        path_lower = path.lower()
        basename = os.path.basename(path).lower()
        for proc in psutil.process_iter(['pid', 'name', 'exe', 'create_time']):
            try:
                proc_name = proc.info['name'].lower()
                if basename in proc_name:
                    if time.time() - proc.info['create_time'] < 2:
                        self.process_watcher.authorize_executable(path, proc.pid)
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

    def shutdown_computer(self):
        QMessageBox.critical(None, "Échec", "Vous avez échoué 3 fois à la traduction. L'ordinateur va s'éteindre dans 10 secondes.")
        if sys.platform == 'win32':
            os.system('shutdown /s /t 10 /c "Vous avez échoué 3 fois à la traduction. L\'ordinateur va s\'éteindre dans 10 secondes."')
            
    def on_executable_launched(self, exec):
        self.create_translation_dialog(exec)
    
    def hide_to_tray(self):
        self.hide()
        self.tray_icon.showMessage(
            "Application minimisée", 
            "L'application continue de surveiller les exécutables en arrière-plan.", 
            QSystemTrayIcon.Information, 
            3000
        )

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Quitter', 
            "Êtes-vous sûr de vouloir quitter? L'application ne surveillera plus les exécutables.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.process_watcher.stop()
            event.accept()
        else:
            event.ignore()

    def add_executable(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Sélectionner un exécutable", 
            os.path.expanduser("~"), 
            "Exécutables (*.exe);;Tous les fichiers (*.*)" if sys.platform == 'win32' else "Tous les fichiers (*.*)"
        )
        if not file_path:
            return
        name, ok = QInputDialog.getText(
            self, 
            "Nom de l'exécutable", 
            "Entrez un nom pour cet exécutable:", 
            QLineEdit.Normal, 
            os.path.basename(file_path).split('.')[0]
        )
        if not ok or not name:
            return
        exec = Executable(name, file_path)
        self.executables.append(exec)
        self.save_executables()
        self.update_executables_list()
        QMessageBox.information(self, "Succès", "Exécutable ajouté avec succès!")

    def remove_executable(self):
        row = self.executables_list.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Attention", "Veuillez sélectionner un exécutable à supprimer.")
            return
        self.executables.pop(row)
        self.save_executables()
        self.update_executables_list()
        QMessageBox.information(self, "Succès", "Exécutable supprimé avec succès!")
    
    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange and self.windowState() & Qt.WindowMinimized:
            event.ignore()
            self.hide_to_tray()
        else:
            super().changeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("English Learning App")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("VotreOrganisation")
    
    main_window = EnglishLearningApp()
    main_window.show()
    
    sys.exit(app.exec_())