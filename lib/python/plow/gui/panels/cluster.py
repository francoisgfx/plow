import os
import logging
from functools import partial 

import plow.client
import plow.gui.constants as constants

from plow.gui.manifest import QtCore, QtGui
from plow.gui.panels import Panel
from plow.gui.util import formatPercentage, copyToClipboard
from plow.gui.event import EventManager
from plow.gui.common import models
from plow.gui.common.widgets import CheckableComboBox, SimplePercentageBarDelegate, \
                                    ManagedListWidget, BooleanCheckBox, FormWidgetLabel, \
                                    TreeWidget


LOGGER = logging.getLogger(__name__)


class ClusterPanel(Panel):

    def __init__(self, name="Clusters", parent=None):
        Panel.__init__(self, name, "Clusters", parent)

        self.setAttr("refreshSeconds", 10)

        self.setWidget(ClusterWidget(self.attrs, self))
        self.setWindowTitle(name)

    def init(self):
        # TODO
        # sweep button (remove finished)
        # refresh button
        # seperator
        # kill button (multi-select)
        # comment button (multi-select)
        #
        titleBar = self.titleBarWidget() 
        titleBar.addAction(QtGui.QIcon(":/images/settings.png"), 
                                       "Edit Selected Cluster Configuration", 
                                       self.openClusterPropertiesDialog)

        titleBar.addAction(QtGui.QIcon(":/images/locked.png"), 
                                       "Lock Selected Clusters", 
                                       partial(self.__setClusterLocked, True))

        titleBar.addAction(QtGui.QIcon(":/images/unlocked.png"), 
                                       "Unlock Selected Clusters", 
                                       partial(self.__setClusterLocked, False))

    def openLoadDialog(self):
        print "Open search dialog"

    def openClusterPropertiesDialog(self):
        try:
            cluster = self.widget().getSelectedClusters()[0]
            dialog = ClusterPropertiesDialog(cluster)
            if dialog.exec_():
                dialog.save()
                self.refresh()
        except IndexError:
            pass

    def refresh(self):
        self.widget().refresh()

    def __setClusterLocked(self, locked):
        try:
            for cluster in self.widget().getSelectedClusters():
                cluster.lock(locked)
        finally:
            self.refresh()


class ClusterWidget(QtGui.QWidget):

    WIDTH = [250, 90, 70, 70, 70, 70, 70, 150]

    def __init__(self, attrs, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(4,0,4,4)

        self.__attrs = attrs
        
        self.__tree = tree = TreeWidget(self)
        tree.setItemDelegateForColumn(1, SimplePercentageBarDelegate(self))

        self.__model = ClusterModel(self)
        self.__proxy = proxy = models.AlnumSortProxyModel(self)
        proxy.setSortRole(QtCore.Qt.DisplayRole)
        proxy.setSourceModel(self.__model)

        tree.setModel(proxy)
        tree.sortByColumn(0, QtCore.Qt.AscendingOrder)

        for i,v in enumerate(self.WIDTH):
            tree.setColumnWidth(i, v) 

        self.layout().addWidget(self.__tree)

        # connections
        tree.clicked.connect(self.__itemClicked)
        tree.doubleClicked.connect(self.__itemDoubleClicked)

    def getSelectedClusters(self):
        rows = self.__tree.selectionModel().selectedRows()
        return [index.data(self.__model.ObjectRole) for index in rows]

    def refresh(self):
        self.__tree.setSortingEnabled(False)
        self.__model.refresh()
        self.__tree.setSortingEnabled(True)

    def __itemClicked(self, index):
        copyToClipboard(index.data(self.__model.ObjectRole).name)

    def __itemDoubleClicked(self, index):
        uid = index.data(self.__model.IdRole)
        EventManager.ClusterOfInterest.emit(uid)


class ClusterModel(models.PlowTableModel):

    HEADERS = ["Name", "Usage", "Nodes", "Locked", "Repair", "Down", "Cores", "Tags"]

    DISPLAY_CALLBACKS = {
        0 : lambda c: c.name,
        1 : lambda c: [c.total.runCores, c.total.cores],
        2 : lambda c: c.total.nodes,
        3 : lambda c: c.total.lockedNodes,
        4 : lambda c: c.total.repairNodes,
        5 : lambda c: c.total.downNodes,
        6 : lambda c: c.total.cores,
        7 : lambda c: ",".join(c.tags),
    }

    def __init__(self, parent=None):
        super(ClusterModel, self).__init__(parent)

        self.__lastUpdateTime = 0;
        self.__iconLocked = QtGui.QIcon(":/images/locked.png")

    def fetchObjects(self):
        return plow.client.get_clusters()

    def data(self, index, role):
        row = index.row()
        col = index.column()
        cluster = self._items[row]
        
        if role == QtCore.Qt.BackgroundColorRole:
            if cluster.isLocked:
                return constants.BLUE
            elif col == 3 and cluster.total.lockedNodes:
                return constants.BLUE
            elif col == 4 and cluster.total.repairNodes:
                return constants.ORANGE
            elif col == 5 and cluster.total.downNodes:
                return constants.RED

        elif role == QtCore.Qt.DecorationRole and col == 0:
            if cluster.isLocked:
                return self.__iconLocked

        elif role == QtCore.Qt.ToolTipRole:
            if col == 1:
                return "\n".join([
                    "Total Cores: %d" % cluster.total.cores,
                    "Running Cores: %d" % cluster.total.runCores,
                    "Idle Cores: %d" % cluster.total.idleCores,
                    "Usage: %s" % formatPercentage(cluster.total.runCores, cluster.total.cores)
                ])
            if col == 6:
                return "\n".join([
                    "Total Cores: %d" % cluster.total.cores,
                    "Running Cores: %d" % cluster.total.runCores,
                    "Idle Cores: %d" % cluster.total.idleCores,
                    "Up Cores: %d" % cluster.total.upCores,
                    "Down Cores: %d" % cluster.total.downCores,
                    "Repair Cores: %d" % cluster.total.repairCores,
                    "Locked Cores: %d" % cluster.total.lockedCores
                ])
            elif col == 2:
                return "\n".join([
                    "Total Nodes: %d" % cluster.total.nodes,
                    "Up Nodes: %d" % cluster.total.upNodes,
                    "Down Nodes: %d" % cluster.total.downNodes,
                    "Repair Nodes: %d" % cluster.total.repairNodes,
                    "Locked Nodes: %d" % cluster.total.lockedNodes,
                ])

        return super(ClusterModel, self).data(index, role)


class ClusterWidgetConfigDialog(QtGui.QDialog):
    """
    A dialog box that lets you configure how the render job widget.
    """
    def __init__(self, attrs, parent=None):
        pass

class ClusterPropertiesDialog(QtGui.QDialog):
    """
    Dialog box for editing the properties of a single cluster.
    """
    def __init__(self, cluster, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.__cluster = cluster

        self.txt_name = QtGui.QLineEdit(self.__cluster.name, self)
        self.list_tags = ManagedListWidget(cluster.tags, self)
        self.cb_locked = BooleanCheckBox(cluster.isLocked)
        self.cb_default = BooleanCheckBox(cluster.isDefault)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | 
            QtGui.QDialogButtonBox.Cancel);
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtGui.QFormLayout()
        layout.setLabelAlignment(QtCore.Qt.AlignLeft)
        layout.addRow(FormWidgetLabel("Name", "cluster.name"), self.txt_name)
        layout.addRow(FormWidgetLabel("Tags", "cluster.tags"), self.list_tags)
        layout.addRow(FormWidgetLabel("Locked", "cluster.locked"), self.cb_locked)
        layout.addRow(FormWidgetLabel("Default", "cluster.default"), self.cb_default)
        layout.addRow(buttons)
        self.setLayout(layout)

    def save(self):
        try:
            c = self.__cluster
            c.set_name(str(self.txt_name.text()))
            c.set_tags(self.list_tags.getValues())
            c.lock(self.cb_locked.isChecked())
            if self.cb_default.isChecked():
                c.set_default()
        except Exception, e:
            title = "Error Saving Cluster"
            text = str(e)
            QtGui.QMessageBox.critical(self, title, text)
