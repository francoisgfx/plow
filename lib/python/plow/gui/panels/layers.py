import logging

import plow.client
import plow.gui.constants as constants

from plow.gui.manifest import QtCore, QtGui
from plow.gui.panels import Panel
from plow.gui.event import EventManager
from plow.gui.common import models, actions
from plow.gui.common.widgets import TableWidget
from plow.gui.common.job import JobProgressDelegate
from plow.gui.util import copyToClipboard

LOGGER = logging.getLogger(__name__)


class LayerPanel(Panel):

    def __init__(self, name="Layers", parent=None):
        Panel.__init__(self, name, "Layers", parent)

        self.__lastJobId = None

        self.setAttr("refreshSeconds", 5)

        self.setWidget(LayerWidget(self.attrs, self))
        self.setWindowTitle(name)

        EventManager.JobOfInterest.connect(self.__handleJobOfInterestEvent)

    def refresh(self):
        self.widget().refresh()

    def __handleJobOfInterestEvent(self, *args, **kwargs):
        jobId = args[0]
        self.widget().setJobId(jobId)
        self.__lastJobId = jobId


#########################
# LayerWidget
#########################
class LayerWidget(QtGui.QWidget):

    WIDTH = [220, 90, 90, 90, 60, 60, 60, 60, 60, 65]

    def __init__(self, attrs, parent=None):
        super(LayerWidget, self).__init__(parent)
        
        self.__attrs = attrs

        self.__view = table = TableWidget(self)
        table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        delegate = JobProgressDelegate(dataRole=LayerModel.ObjectRole, parent=self)
        table.setItemDelegateForColumn(LayerModel.HEADERS.index('Progress'), delegate)

        self.__jobId = None
        self.__model = None

        self.__proxy = proxy = models.AlnumSortProxyModel(self)
        proxy.setSortRole(LayerModel.DataRole)
        table.setModel(proxy)

        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(4,0,4,4)
        layout.addWidget(table)

        # connections
        table.customContextMenuRequested.connect(self.__showContextMenu)
        table.clicked.connect(self.__itemClicked)
        table.doubleClicked.connect(self.__itemDoubleClicked)

    def refresh(self):
        if self.__model:
            self.__view.setSortingEnabled(False)
            self.__model.refresh()
            self.__view.setSortingEnabled(True)

    def getSelectedLayers(self):
        rows = self.__view.selectionModel().selectedRows()
        return [index.data(self.__model.ObjectRole) for index in rows]

    def setJobId(self, jobid):
        self.__view.sortByColumn(-1, QtCore.Qt.AscendingOrder)

        new_model = False
        if not self.__model:
            self.__model = LayerModel(self)
            self.__proxy.setSourceModel(self.__model)
            new_model = True

        self.__jobId = jobid
        self.__model.setJob(jobid)
        
        if new_model:
            table = self.__view
            for i, w in enumerate(self.WIDTH):
                table.setColumnWidth(i, w)

    def __selectedCount(self):
        s_model = self.__view.selectionModel()
        return len(s_model.selectedRows())

    def __itemClicked(self, index):
        copyToClipboard(index.data(self.__model.ObjectRole).name)

    def __itemDoubleClicked(self, index):
        uid = index.data(self.__model.ObjectRole).id
        EventManager.LayerOfInterest.emit(uid)

    def __showContextMenu(self, pos):
        menu = QtGui.QMenu()

        total = self.__selectedCount()
        if 1 <= total <= 2:
            icon = QtGui.QIcon(":/images/depend.png")
            depend = menu.addAction(icon, "Add Dependencies", self.__addDepends)

        menu.addAction(QtGui.QIcon(":/images/depend.png"), "Drop Depends", self.__dropDepends)

        menu.exec_(self.mapToGlobal(pos))

    def __addDepends(self):
        layers = self.getSelectedLayers()
        actions.launchDependsWizard(layers, parent=self)

    def __dropDepends(self):
        layers = self.getSelectedLayers()
        actions.dropDepends(layers, ask=True, parent=self)


class LayerModel(models.PlowTableModel):

    HEADERS = [
        "Name", "Range", "Service", "Tags", "Total", "Pend", "Run", 
        "Dead", "Cores", "AvgTime", "Progress"
    ]

    DISPLAY_CALLBACKS = {
        0: lambda l: l.name,
        1: lambda l: "%s (%d)" % (l.range, l.chunk) if l.range else "-",
        2: lambda l: l.service,
        3: lambda l: ', '.join(l.tags),
        4: lambda l: l.totals.total,
        5: lambda l: l.totals.waiting + l.totals.depend,
        6: lambda l: l.totals.running,
        7: lambda l: l.totals.dead,
        8: lambda l: l.runCores,
        9: lambda l: "{0:.1f}".format(l.stats.avgClockTime / 3600000.0), # msec => hour
    }

    def __init__(self, parent=None):
        super(LayerModel, self).__init__(parent)

        self.__jobId = None

        # Layers are updated incrementally, so don't 
        # remove missing ones
        self.refreshShouldRemove = False

    def fetchObjects(self):
        if not self.__jobId:
            return []

        layers = plow.client.get_layers(self.__jobId)
        return layers   

    def getJobId(self):
        return self.__jobId

    def setJob(self, jobid):
        self.__jobId = jobid
        self.__lastUpdateTime = 0

        layers = self.fetchObjects()
        self.setItemList(layers)

    def refresh(self):
        if not self.__jobId:
            return

        super(LayerModel, self).refresh()

    def data(self, index, role):
        row = index.row()
        col = index.column()
        layer = self._items[row]

        if col == 7 and role == QtCore.Qt.BackgroundRole:
            if layer.totals.dead:
                dead = plow.client.TaskState.DEAD
                return constants.COLOR_TASK_STATE[dead]

        if role == QtCore.Qt.ToolTipRole:
            try:
                return self.DISPLAY_CALLBACKS[col](layer)
            except KeyError:
                pass

        return super(LayerModel, self).data(index, role)

