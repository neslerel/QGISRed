# -*- coding: utf-8 -*-
from qgis.gui import QgsMessageBar
from qgis.core import QgsVectorLayer, QgsProject, QgsLayerTreeLayer
from qgis.PyQt import QtGui, uic
from PyQt5.QtWidgets import QMessageBox, QTableWidgetItem, QDialog
from PyQt5.QtCore import QFileInfo
from qgis.core import QgsTask, QgsApplication
# Import the code for the dialog
from .qgisred_newproject_dialog import QGISRedNewProjectDialog
from .qgisred_import_dialog import QGISRedImportDialog
from .qgisred_importproject_dialog import QGISRedImportProjectDialog
from .qgisred_cloneproject_dialog import QGISRedCloneProjectDialog
from ..tools.qgisred_utils import QGISRedUtils
import os
import datetime
from time import strftime
from shutil import copyfile

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'qgisred_projectmanager_dialog.ui'))

class QGISRedProjectManagerDialog(QDialog, FORM_CLASS):
    #Common variables
    iface = None
    NetworkName = ""
    ProjectDirectory = ""
    ProcessDone= False
    gplFile=""
    ownMainLayers = ["Pipes", "Valves", "Pumps", "Junctions", "Tanks", "Reservoirs", "Demands", "Sources"]
    layerExtensions = [".shp", ".dbf", ".shx", ".prj", ".qpj"]
    ownFiles = ["DefaultValues.dbf", "Options.dbf", "Rules.dbf", "Controls.dbf", "Curves.dbf", "Patterns.dbf", "TitleAndNotes.txt" ]
    
    def __init__(self, parent=None):
        """Constructor."""
        super(QGISRedProjectManagerDialog, self).__init__(parent)
        self.setupUi(self)
        self.btCreate.clicked.connect(self.createProject)
        self.btImport.clicked.connect(self.importData)
        self.btOpen.clicked.connect(self.openProject)
        self.btClone.clicked.connect(self.cloneProject)
        
        self.btLoad.clicked.connect(self.importProject)
        self.btUnLoad.clicked.connect(self.deleteProject)
        self.btGo2Folder.clicked.connect(self.openFolder)
        #Variables:
        gplFolder = os.path.join(os.popen('echo %appdata%').read().strip(), "QGISRed")
        try: #create directory if does not exist
            os.stat(gplFolder)
        except:
            os.mkdir(gplFolder) 
        self.gplFile = os.path.join(gplFolder, "qgisredprojectlist.gpl")
        #Columns:
        self.twProjectList.setColumnCount(4)
        item = QTableWidgetItem("Network's Name")
        self.twProjectList.setHorizontalHeaderItem(0,item)
        item = QTableWidgetItem("Last update")
        self.twProjectList.setHorizontalHeaderItem(1,item)
        item = QTableWidgetItem("Creation date")
        self.twProjectList.setHorizontalHeaderItem(2,item)
        item = QTableWidgetItem("Folder")
        self.twProjectList.setHorizontalHeaderItem(3,item)
        #Rows:
        self.fillTable()
        self.twProjectList.cellDoubleClicked.connect(self.openProject)
        #self.twProjectList.customContextMenuRequested.connect(self.openFolder)

    def config(self, ifac, direct, netw, parent):
        self.parent = parent
        self.iface=ifac
        self.ProcessDone = False
        self.NetworkName = netw
        self.ProjectDirectory = direct
        
        for row in range(0,self.twProjectList.rowCount()):
            if self.ProjectDirectory.replace("/","\\") == str(self.twProjectList.item(row,3).text()) and self.NetworkName == str(self.twProjectList.item(row,0).text()):
                self.twProjectList.setCurrentCell(row, 1)
                break

    def fillTable(self):
        self.twProjectList.setRowCount(0)
        if not os.path.exists(self.gplFile):
            f1 = open(self.gplFile, "w+")
            f1.close()
        validLines= []
        f = open(self.gplFile, "r")
        
        notDuplicateLines = []
        seen = set()
        for value in f:
            if value not in seen:
                notDuplicateLines.append(value)
                seen.add(value)
        
        for x in notDuplicateLines:
            values = x.split(";")
            if len(values) == 2:
                values[1] = values[1].rstrip("\r\n")
                pp = os.path.realpath(os.path.join(values[1], values[0] + ".gqp"))
                if os.path.exists(pp):
                    validLines.append(x)
                    f2= open (pp, "r")
                    lines = f2.readlines()
                    if len(lines)>= 2:
                        rowPosition = self.twProjectList.rowCount()
                        self.twProjectList.insertRow(rowPosition)
                        self.twProjectList.setItem(rowPosition , 0, QTableWidgetItem(values[0]))
                        self.twProjectList.setItem(rowPosition , 1, QTableWidgetItem(lines[1]))
                        self.twProjectList.setItem(rowPosition , 2, QTableWidgetItem(lines[0]))
                        self.twProjectList.setItem(rowPosition , 3, QTableWidgetItem(values[1]))
        f.close()
        f = open(self.gplFile, "w")
        for x in validLines:
            QGISRedUtils().writeFile(f, x)
        f.close()

    def addProjectToTable(self, file, folder, net):
        valid = True
        if not file=="":
            folder= os.path.dirname(file)
            net = os.path.splitext(os.path.basename(file))[0]
        else:
            valid=False
            dirList = os.listdir(folder)
            for layerName in self.ownMainLayers:
                valid = valid or net + "_" + layerName + ".shp" in dirList
            if valid:
                self.createGqpFile(net,folder)
        if valid:
            file = open(self.gplFile, "a+")
            QGISRedUtils().writeFile(file, net + ";" + folder.replace("/","\\") + "\n")
            file.close()
            self.fillTable()

    def createGqpFile(self, net, folder):
        f = open(os.path.join(folder, net + ".gqp"), "w+")
        f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
        f.write(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
        QGISRedUtils().writeFile(f, "[" + net + " Inputs]\n")
        dirList = os.listdir(folder)
        # for fileName in self.ownFiles:
            # if ".dbf" in fileName:
                # if net + "_" + fileName in dirList:
                    # QGISRedUtils().writeFile(f, os.path.join(folder, net + "_" + fileName) + '\n')
        for layerName in self.ownMainLayers:
            if net + "_" + layerName + ".shp" in dirList:
                QGISRedUtils().writeFile(f, os.path.join(folder, net + "_" + layerName + ".shp") + '\n')
        f.close()

    def clearQGisProject(self,task):
        QgsProject.instance().clear()
        raise Exception('')

    def loadGplFile(self, projectDirectory, networkName):
        gqpFilename = os.path.join(projectDirectory, networkName + ".gqp")
        if os.path.exists(gqpFilename):
            f = open(gqpFilename, "r")
            lines = f.readlines()
            qgsFile = lines[2]
            if ".qgs" in qgsFile or ".qgz" in qgsFile:
                finfo = QFileInfo(qgsFile)
                QgsProject.instance().read(finfo.filePath())
            else:
                group = None
                for i in range(2, len(lines)):
                    if "[" in lines[i]:
                        groupName = str(lines[i].strip("[").strip("\r\n").strip("]")).replace(networkName + " ", "")
                        root = QgsProject.instance().layerTreeRoot()
                        netGroup = root.addGroup(networkName)
                        group= netGroup.addGroup(groupName)
                    else:
                        layerPath= lines[i].strip("\r\n")
                        if not os.path.exists(layerPath):
                            continue
                        vlayer = None
                        layerName = os.path.splitext(os.path.basename(layerPath))[0].replace(networkName + "_", "")
                        if group is None:
                            vlayer = self.iface.addVectorLayer(layerPath, layerName, "ogr")
                        else:
                            vlayer = QgsVectorLayer(layerPath, layerName, "ogr")
                            QgsProject.instance().addMapLayer(vlayer, False)
                            group.insertChildNode(0, QgsLayerTreeLayer(vlayer))
                        if not vlayer is None:
                            if ".shp" in layerPath:
                                names = (os.path.splitext(os.path.basename(layerPath))[0]).split("_")
                                nameLayer = names[len(names)-1]
                                QGISRedUtils().setStyle(vlayer, nameLayer.lower())
        else:
            self.iface.messageBar().pushMessage("Warning", "File not found", level=1, duration=5)

    def createProject(self):
        valid = self.parent.isOpenedProject()
        if valid:
            task1 = QgsTask.fromFunction('Dismiss this message', self.clearQGisProject, on_finished=self.createProjectProcess)
            task1.run()
            QgsApplication.taskManager().addTask(task1)

    def createProjectProcess(self, exception=None, result=None):
        dlg = QGISRedNewProjectDialog()
        dlg.config(self.iface, "Temporal folder", "Network")
        # Run the dialog event loop
        self.close()
        dlg.exec_()
        result = dlg.ProcessDone
        if result:
            self.ProjectDirectory = dlg.ProjectDirectory
            self.NetworkName = dlg.NetworkName
            self.ProcessDone = True

    def importData(self):
        dlg = QGISRedImportDialog()
        dlg.config(self.iface, self.ProjectDirectory, self.NetworkName, self.parent)
        # Run the dialog event loop
        self.close()
        dlg.exec_()
        result = dlg.ProcessDone
        if result:
            self.ProjectDirectory = dlg.ProjectDirectory
            self.NetworkName = dlg.NetworkName
            self.ProcessDone = True

    def deleteProject(self):
        selectionModel = self.twProjectList.selectionModel()
        if selectionModel.hasSelection():
            for row in selectionModel.selectedRows():
                if self.ProjectDirectory.replace("/","\\") == str(self.twProjectList.item(row.row(),3).text()) and self.NetworkName == str(self.twProjectList.item(row.row(),0).text()):
                    self.iface.messageBar().pushMessage("Warning", "Current project can not be deleted.", level=1, duration=5)
                    return
                if os.path.exists(self.gplFile):
                    f = open(self.gplFile, "r")
                    lines = f.readlines()
                    f.close()
                    f = open(self.gplFile, "w")
                    i=0
                    for line in lines:
                        if not i==row.row():
                            QGISRedUtils().writeFile(f, line)
                        i=i+1
                    f.close()
            self.fillTable()

    def importProject(self):
        dlg = QGISRedImportProjectDialog()
        # Run the dialog event loop
        dlg.exec_()
        result = dlg.ProcessDone
        if result:
            path=""
            name=""
            valid = True
            # if dlg.IsFile:
                # self.addProjectToTable(dlg.File, "", "")
            # else:
            self.addProjectToTable("", dlg.ProjectDirectory, dlg.NetworkName)

    def openProject(self):
        selectionModel = self.twProjectList.selectionModel()
        if selectionModel.hasSelection():
            valid = self.parent.isOpenedProject()
            if valid:
                task1 = QgsTask.fromFunction('Dismiss this message', self.clearQGisProject, on_finished=self.openProjectProcess)
                task1.run()
                QgsApplication.taskManager().addTask(task1)
        else:
            self.iface.messageBar().pushMessage("Warning", "You need to select a valid project to open it.", level=1, duration=5)

    def openProjectProcess(self, exception=None, result=None):
        selectionModel = self.twProjectList.selectionModel()
        for row in selectionModel.selectedRows():
            rowIndex = row.row()
            self.NetworkName = str(self.twProjectList.item(rowIndex, 0).text())
            self.ProjectDirectory = str(self.twProjectList.item(rowIndex, 3).text())
            self.loadGplFile(self.ProjectDirectory, self.NetworkName)
            break
        self.close()
        self.ProcessDone = True

    def cloneProject(self):
        selectionModel = self.twProjectList.selectionModel()
        if selectionModel.hasSelection():
            for row in selectionModel.selectedRows():
                mainName= str(self.twProjectList.item(row.row(), 0).text())
                mainFolder = str(self.twProjectList.item(row.row(), 3).text())
                dlg = QGISRedCloneProjectDialog()
                # Run the dialog event loop
                dlg.exec_()
                result = dlg.ProcessDone
                if result:
                    if mainName == dlg.NetworkName:
                        self.iface.messageBar().pushMessage("Warning", "Selected project has the same Network's Name. Plase, set another name.", level=1, duration=5)
                    else:
                        for layerName in self.ownMainLayers:
                            layerPath = os.path.join(mainFolder, mainName + "_" + layerName)
                            #Extensions
                            for ext in self.layerExtensions:
                                if os.path.exists(layerPath + ext):
                                    copyfile(layerPath + ext, os.path.join(dlg.ProjectDirectory, dlg.NetworkName + "_" + layerName + ext))
                        for fileName in self.ownFiles:
                            filePath = os.path.join(mainFolder, mainName + "_" + fileName)
                            if os.path.exists(filePath):
                                    copyfile(filePath, os.path.join(dlg.ProjectDirectory, dlg.NetworkName + "_" + fileName))

                        self.addProjectToTable("", dlg.ProjectDirectory, dlg.NetworkName)
                break
        else:
            self.iface.messageBar().pushMessage("Warning", "There is no a selected project to clone.", level=1, duration=5)

    def openFolder(self):
        selectionModel = self.twProjectList.selectionModel()
        if selectionModel.hasSelection():
            for row in selectionModel.selectedRows():
                mainFolder = str(self.twProjectList.item(row.row(), 3).text())
                os.startfile(mainFolder)