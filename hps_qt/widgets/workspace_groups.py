from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget


class WorkspaceGroups(QWidget):
    """
    Groups the growing toolset into four professional workspaces:
    Produce, Project, AI, Control.
    """
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        self.main_tabs = QTabWidget()
        layout.addWidget(self.main_tabs)

        self.produce = QTabWidget()
        self.project = QTabWidget()
        self.ai = QTabWidget()
        self.control = QTabWidget()

        self.main_tabs.addTab(self.produce, "Produce")
        self.main_tabs.addTab(self.project, "Project")
        self.main_tabs.addTab(self.ai, "AI")
        self.main_tabs.addTab(self.control, "Control")

    def add_produce(self, widget, title):
        self.produce.addTab(widget, title)

    def add_project(self, widget, title):
        self.project.addTab(widget, title)

    def add_ai(self, widget, title):
        self.ai.addTab(widget, title)

    def add_control(self, widget, title):
        self.control.addTab(widget, title)

    def addTab(self, widget, title):
        # Compatibility fallback for old code paths.
        self.add_project(widget, title)

    def indexOf(self, widget):
        # Compatibility fallback. Returns -1 because focus_widget should be used.
        return -1

    def setCurrentIndex(self, idx):
        self.main_tabs.setCurrentIndex(idx)

    def focus_widget(self, widget):
        for outer_idx, tab in enumerate([self.produce, self.project, self.ai, self.control]):
            for i in range(tab.count()):
                if tab.widget(i) is widget:
                    self.main_tabs.setCurrentIndex(outer_idx)
                    tab.setCurrentIndex(i)
                    return True
        return False
