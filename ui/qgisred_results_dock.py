# -*- coding: utf-8 -*-
from qgis.gui import QgsMessageBar
from qgis.core import QgsVectorLayer, QgsProject, QgsCoordinateReferenceSystem
from qgis.PyQt import QtGui, uic
from qgis.core import Qgis, QgsTask, QgsApplication
from PyQt5.QtWidgets import QDockWidget, QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from qgis.core import QgsSvgMarkerSymbolLayer, QgsSymbol, QgsSingleSymbolRenderer, QgsLineSymbol, QgsProperty, QgsRenderContext, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling
from qgis.core import QgsSimpleLineSymbolLayer, QgsMarkerSymbol, QgsMarkerLineSymbolLayer, QgsSimpleMarkerSymbolLayer
from qgis.core import QgsGraduatedSymbolRenderer, QgsGradientColorRamp as QgsVectorGradientColorRamp, QgsRendererRange
from ..tools.qgisred_utils import QGISRedUtils
import os
from ctypes import*
from time import sleep
import tempfile
from shutil import copyfile

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'qgisred_results_dock.ui'))


class QGISRedResultsDock(QDockWidget, FORM_CLASS):
    #Common variables
    iface = None
    NetworkName = ""
    ProjectDirectory = ""
    ownMainLayers = ["Pipes", "Valves", "Pumps", "Junctions", "Tanks", "Reservoirs"]
    LabelResults= {}
    IndexTime= {}
    Comments= {}
    Renders={}
    Variables=""
    Computing=False
    TimeLabels=[]
    LabelsToOpRe=[]
    def __init__(self, iface):
        """Constructor."""
        super(QGISRedResultsDock, self).__init__(iface.mainWindow())
        self.iface = iface
        self.setupUi(self)
        
        self.btMoreTime.clicked.connect(self.nextTime)
        self.btLessTime.clicked.connect(self.previousTime)
        self.cbTimes.currentIndexChanged.connect(self.timeChanged)
        
        self.cbLinks.currentIndexChanged.connect(self.linksChanged)
        self.cbNodes.currentIndexChanged.connect(self.nodesChanged)
        self.cbLinkLabels.clicked.connect(self.linkLabelsClicked)
        self.cbNodeLabels.clicked.connect(self.nodeLabelsClicked)
        self.cbFlowDirections.clicked.connect(self.flowDirectionsClicked)
        self.btSaveScenario.clicked.connect(self.saveScenario)
        self.cbScenarios.currentIndexChanged.connect(self.scenarioChanged)
        self.btDeleteScenario.clicked.connect(self.deleteScenario)

    def config(self, direct, netw, labels, baseLayers):
        self.Computing=True
        if not (self.NetworkName == netw and self.ProjectDirectory == direct):
            self.LabelResults={}
            self.IndexTime= {}
            self.cbScenarios.clear()
            self.cbScenarios.addItem("Base")
            self.NetworkName = netw
            self.ProjectDirectory = direct
            self.readSavedScenarios()
        
        #CRS
        crs = self.iface.mapCanvas().mapSettings().destinationCrs()
        if crs.srsid()==0:
            crs = QgsCoordinateReferenceSystem()
            crs.createFromId(3452, QgsCoordinateReferenceSystem.InternalCrsId)
        self.CRS=crs
        
        self.NetworkName = netw
        self.ProjectDirectory = direct
        self.cbScenarios.setCurrentIndex(0)
        self.btDeleteScenario.setEnabled(False)
        
        self.LabelsToOpRe = baseLayers
        if len(self.LabelsToOpRe)==0:
            self.cbLinks.setCurrentIndex(1)
            self.cbFlowDirections.setVisible(True)
            self.cbNodes.setCurrentIndex(1)
        else:
            for nameLayer in self.LabelsToOpRe:
                if nameLayer == "Link_Flow":
                    self.cbLinks.setCurrentIndex(1)
                    self.cbFlowDirections.setVisible(True)
                if nameLayer == "Link_Velocity":
                    self.cbLinks.setCurrentIndex(2)
                if nameLayer == "Link_HeadLoss":
                    self.cbLinks.setCurrentIndex(3)
                if nameLayer == "Link_Quaility":
                    self.cbLinks.setCurrentIndex(4)
                if nameLayer == "Node_Pressure":
                    self.cbNodes.setCurrentIndex(1)
                if nameLayer == "Node_Head":
                    self.cbNodes.setCurrentIndex(2)
                if nameLayer == "Node_Demand":
                    self.cbNodes.setCurrentIndex(3)
                if nameLayer == "Node_Quaility":
                    self.cbNodes.setCurrentIndex(4)
        
        list = labels.split(';')
        self.TimeLabels =[]
        self.cbTimes.clear()
        if len(list)==1:
            self.TimeLabels.append("Permanent")
            self.cbTimes.addItem("Permanent")
        else:
            for item in list:
                self.TimeLabels.append(self.insert(self.insert(item, " ", 6), " ", 3))
                self.cbTimes.addItem(self.insert(self.insert(item, " ", 6), " ", 3))
        self.LabelResults["Base"]= self.TimeLabels
        self.Comments["Base"]= "Last results computed"
        self.lbComments.setText(self.Comments["Base"])
        self.writeScenario("Base", self.TimeLabels, self.Comments["Base"])
        
        if len(list)==1:
            self.lbLabel5.setVisible(False)
            self.btLessTime.setVisible(False)
            self.btMoreTime.setVisible(False)
            self.cbTimes.setVisible(False)
            #self.btPlay.setVisible(False)
        else:
            self.lbLabel5.setVisible(True)
            self.btLessTime.setVisible(True)
            self.btMoreTime.setVisible(True)
            self.cbTimes.setVisible(True)
            #self.btPlay.setVisible(True)
        self.IndexTime["Base"]=0
        self.cbTimes.setCurrentIndex(0)
        #self.lbTime.setVisible(True)
        self.lbTime.setText(self.TimeLabels[0])
        self.Computing = False
        #Open results
        self.Scenario = "Base"
        self.saveCurrentRender(True)
        self.openAllResults()

    def isCurrentProject(self):
        currentNetwork =""
        currentDirectory = ""
        layers = [tree_layer.layer() for tree_layer in QgsProject.instance().layerTreeRoot().findLayers()]
        
        for layer in layers:
            layerUri= layer.dataProvider().dataSourceUri().split("|")[0]
            self.CRS = layer.crs()
            for layerName in self.ownMainLayers:
                if "_" + layerName in layerUri:
                    currentDirectory = os.path.dirname(layerUri)
                    vectName = os.path.splitext(os.path.basename(layerUri))[0].split("_")
                    name =""
                    for part in vectName:
                        if part in self.ownMainLayers:
                            break
                        name = name + part + "_"
                    name = name.strip("_")
                    currentNetwork = name
                    if self.NetworkName == currentNetwork and self.ProjectDirectory == currentDirectory:
                        return True
                    else:
                        self.iface.messageBar().pushMessage("Warning", "The current project has been changed. Please, try again.", level=1, duration=5)
                        self.close()
                        return False

        self.iface.messageBar().pushMessage("Warning", "The current project has been changed. Please, try again.", level=1, duration=5)
        self.close()
        return False

    def openLayerResults(self, scenario):
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        utils = QGISRedUtils(resultPath, self.NetworkName + "_" + scenario, self.iface)
        resultGroup = self.getResultGroup()
        group = resultGroup.findGroup(scenario)
        if group is None:
            group = resultGroup.addGroup(scenario)
        for file in self.LabelsToOpRe:
            utils.openLayer(self.CRS, group, file, results=True)

    def removeResults(self, task):
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        utils = QGISRedUtils(resultPath, self.NetworkName +"_" + self.Scenario, self.iface)
        utils.removeLayers(self.LabelsToOpRe)
        if task is not None:
            raise Exception('')

    def getResultGroup(self):
        resultGroup = QgsProject.instance().layerTreeRoot().findGroup("Results")
        if resultGroup is None:
            netGroup = QgsProject.instance().layerTreeRoot().findGroup(self.NetworkName)
            if netGroup is None:
                root = QgsProject.instance().layerTreeRoot()
                netGroup = root.addGroup(self.NetworkName)
            resultGroup = netGroup.insertGroup(0,"Results")
        resultGroup.setItemVisibilityChecked(True)
        return resultGroup

    def setVariablesTimes(self):
        self.Variables=""
        if self.cbLinks.currentIndex()==1:
            self.Variables=self.Variables + "Flow_Link;"
        if self.cbLinks.currentIndex()==2:
            self.Variables=self.Variables + "Velocity_Link;"
        if self.cbLinks.currentIndex()==3:
            self.Variables=self.Variables + "HeadLoss_Link;"
        if self.cbLinks.currentIndex()==4:
            self.Variables=self.Variables + "Quality_Link;"
        if self.cbNodes.currentIndex()==1:
            self.Variables=self.Variables + "Pressure_Node;"
        if self.cbNodes.currentIndex()==2:
            self.Variables=self.Variables + "Head_Node;"
        if self.cbNodes.currentIndex()==3:
            self.Variables=self.Variables + "Demand_Node;"
        if self.cbNodes.currentIndex()==4:
            self.Variables=self.Variables + "Quality_Node;"
        
        if self.Variables=="":
            self.iface.messageBar().pushMessage("Validations", "No variable results selected", level=1)
            return False
        return True

    def setLayersNames(self, all=False):
        self.LabelsToOpRe = []
        if self.cbLinks.currentIndex()==1 or all:
            self.LabelsToOpRe.append("Link_" + "Flow")
        if self.cbLinks.currentIndex()==2 or all:
            self.LabelsToOpRe.append("Link_" + "Velocity")
        if self.cbLinks.currentIndex()==3 or all:
            self.LabelsToOpRe.append("Link_" + "HeadLoss")
        if self.cbLinks.currentIndex()==4 or all:
            self.LabelsToOpRe.append("Link_" + "Quaility")
        if self.cbNodes.currentIndex()==1 or all:
            self.LabelsToOpRe.append("Node_" + "Pressure")
        if self.cbNodes.currentIndex()==2 or all:
            self.LabelsToOpRe.append("Node_" + "Head")
        if self.cbNodes.currentIndex()==3 or all:
            self.LabelsToOpRe.append("Node_" + "Demand")
        if self.cbNodes.currentIndex()==4 or all:
            self.LabelsToOpRe.append("Node_" + "Quaility")
        return self.LabelsToOpRe

    def setLinksLayersNames(self):
        self.LabelsToOpRe = []
        self.LabelsToOpRe.append("Link_" + "Flow")
        self.LabelsToOpRe.append("Link_" + "Velocity")
        self.LabelsToOpRe.append("Link_" + "HeadLoss")
        self.LabelsToOpRe.append("Link_" + "Quaility")

    def setNodesLayersNames(self):
        self.LabelsToOpRe = []
        self.LabelsToOpRe.append("Node_" + "Pressure")
        self.LabelsToOpRe.append("Node_" + "Head")
        self.LabelsToOpRe.append("Node_" + "Demand")
        self.LabelsToOpRe.append("Node_" + "Quaility")

    def insert(self, source_str, insert_str, pos):
        return source_str[:pos]+insert_str+source_str[pos:]

    def restoreElementsCb(self):
        self.Scenario = self.cbScenarios.currentText()
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        self.setLayersNames(True)
        layers = [tree_layer.layer() for tree_layer in QgsProject.instance().layerTreeRoot().findLayers()]
        
        self.Computing = True
        self.cbLinks.setCurrentIndex(0)
        self.cbNodes.setCurrentIndex(0)
        self.cbFlowDirections.setVisible(False)

        for nameLayer in self.LabelsToOpRe:
            for layer in layers:
                if str(layer.dataProvider().dataSourceUri().split("|")[0]).replace("/","\\")== os.path.join(resultPath, self.NetworkName + "_" + self.Scenario + "_" + nameLayer + ".shp").replace("/","\\"):
                    if nameLayer == "Link_Flow":
                        self.cbLinks.setCurrentIndex(1)
                        self.cbFlowDirections.setVisible(True)
                    if nameLayer == "Link_Velocity":
                        self.cbLinks.setCurrentIndex(2)
                    if nameLayer == "Link_HeadLoss":
                        self.cbLinks.setCurrentIndex(3)
                    if nameLayer == "Link_Quaility":
                        self.cbLinks.setCurrentIndex(4)
                    if nameLayer == "Node_Pressure":
                        self.cbNodes.setCurrentIndex(1)
                    if nameLayer == "Node_Head":
                        self.cbNodes.setCurrentIndex(2)
                    if nameLayer == "Node_Demand":
                        self.cbNodes.setCurrentIndex(3)
                    if nameLayer == "Node_Quaility":
                        self.cbNodes.setCurrentIndex(4)
        self.Computing = False

    def saveCurrentRender(self, all=False):
        layers = [tree_layer.layer() for tree_layer in QgsProject.instance().layerTreeRoot().findLayers()]
        
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        if all:
            self.setLayersNames(True)
        dictSce = self.Renders.get(self.Scenario)
        if dictSce is None:
            dictSce ={}
        for nameLayer in self.LabelsToOpRe:
            for layer in layers:
                pathLayer = str(layer.dataProvider().dataSourceUri().split("|")[0])
                if pathLayer== os.path.join(resultPath, self.NetworkName + "_" + self.Scenario + "_" + nameLayer + ".shp"):
                    if dictSce.get(pathLayer) is not None:
                        continue
                    renderer= layer.renderer()
                    if renderer.type() == 'graduatedSymbol':
                        dictSce[pathLayer]= renderer.ranges()
        self.Renders[self.Scenario]=dictSce

    def paintIntervalTimeResults(self, columnNumber, setRender = False):
        if not self.isCurrentProject():
            return
        
        self.Scenario = self.cbScenarios.currentText()
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        
        layers = [tree_layer.layer() for tree_layer in QgsProject.instance().layerTreeRoot().findLayers()]
        
        self.lbTime.setText(self.TimeLabels[columnNumber])
        for nameLayer in self.LabelsToOpRe:
            for layer in layers:
                if str(layer.dataProvider().dataSourceUri().split("|")[0]).replace("/","\\")== os.path.join(resultPath, self.NetworkName + "_" + self.Scenario + "_" + nameLayer + ".shp").replace("/","\\"):
                    field_names = [field.name() for field in layer.fields()]
                    field = field_names[columnNumber+2]
                    self.setGraduadedPalette(layer, field, setRender, nameLayer)
                    #layer.setName(nameLayer + " " + self.TimeLabels[columnNumber])
                    layer.setName(nameLayer.replace("_", " "))
                    layer.setMapTipTemplate(nameLayer.replace("Link_","").replace("Node_","") + ": [% \"T" + str(columnNumber) + "\" %]")
                    self.setLayerLabels(layer, "T" + str(columnNumber))

    def setLayerLabels(self, layer, fieldName):
        if (layer.geometryType()==0 and self.cbNodeLabels.isChecked()) or (layer.geometryType()!=0 and self.cbLinkLabels.isChecked()):
            pal_layer = QgsPalLayerSettings()
            pal_layer.fieldName = fieldName
            pal_layer.enabled = True
            pal_layer.placement = QgsPalLayerSettings.Line
            labels = QgsVectorLayerSimpleLabeling(pal_layer)
            layer.setLabeling(labels)
            layer.setLabelsEnabled(True)
            layer.triggerRepaint()

    def setGraduadedPalette(self, layer, field, setRender, nameLayer):
        try: # QGis 3
            renderer = layer.renderer()
            symbol = renderer.symbol() #SimpleSymbol
        except:
            symbol = renderer.symbols(QgsRenderContext()) #sourceSymbol() #GraduatedSymbol
        
        if setRender:
            prop = QgsProperty()
            if symbol.type()==1: #line
                if "Flow" in layer.name() and self.cbFlowDirections.isChecked():
                    ss = symbol.symbolLayer(3) #arrow positive flow
                    prop.setExpressionString("if(Type='PIPE', if(" + field + ">0,3,0),0)")
                    ss.subSymbol().setDataDefinedSize(prop)
                    ss = symbol.symbolLayer(4) #arrow negative flow
                    prop.setExpressionString("if(Type='PIPE', if(" + field + "<0,3,0),0)")
                    ss.subSymbol().setDataDefinedSize(prop)
                else:
                    prop.setExpressionString("0")
                    symbol.symbolLayer(3).subSymbol().setDataDefinedSize(prop)
                    symbol.symbolLayer(4).subSymbol().setDataDefinedSize(prop)
            else: #point
                prop.setExpressionString("if(Type ='TANK', 7,0)")
                symbol.symbolLayer(0).setDataDefinedProperty(0, prop) #0 = PropertySize
                symbol.symbolLayer(0).setDataDefinedProperty(9, prop) #0 = PropertyWidth
                prop.setExpressionString("if(Type ='RESERVOIR', 7,0)")
                symbol.symbolLayer(1).setDataDefinedProperty(0, prop)
                symbol.symbolLayer(1).setDataDefinedProperty(9, prop)
                prop.setExpressionString("if(Type ='RESERVOIR' or Type='TANK', 0,2)")
                symbol.symbolLayer(2).setDataDefinedProperty(0, prop)
                symbol.symbolLayer(2).setDataDefinedProperty(9, prop)
        else:
            for sym in symbol:
                if sym.type()==1: #line
                    prop = QgsProperty()
                    if "Flow" in layer.name() and self.cbFlowDirections.isChecked():
                        ss = sym.symbolLayer(3) #arrow positive flow
                        prop.setExpressionString("if(Type='PIPE', if(" + field + ">0,3,0),0)")
                        ss.subSymbol().setDataDefinedSize(prop)
                        ss = sym.symbolLayer(4) #arrow negative flow
                        prop.setExpressionString("if(Type='PIPE', if(" + field + "<0,3,0),0)")
                        ss.subSymbol().setDataDefinedSize(prop)
                    else:
                        prop.setExpressionString("0")
                        sym.symbolLayer(3).subSymbol().setDataDefinedSize(prop)
                        sym.symbolLayer(4).subSymbol().setDataDefinedSize(prop)
                else: #point
                    pass
        
        if "Flow" in layer.name():
            field = "abs(" + field + ")"
        if setRender:
            hasRender = False
            dictRend = self.Renders.get(self.Scenario)
            if dictRend is None:
                dictRend = self.Renders.get("Base")
                if dictRend is not None:
                    ranges = dictRend.get(str(layer.dataProvider().dataSourceUri().split("|")[0]).replace("_" + self.Scenario + "_","_Base_"))
                    if ranges is not None:
                        hasRender= True
            else:
                ranges = dictRend.get(str(layer.dataProvider().dataSourceUri().split("|")[0]))
                if ranges is not None:
                    hasRender=True
                else:
                    dictRend = self.Renders.get("Base")
                    if dictRend is not None:
                        ranges = dictRend.get(str(layer.dataProvider().dataSourceUri().split("|")[0]).replace("_" + self.Scenario + "_","_Base_"))
                        if ranges is not None:
                            hasRender= True
            if hasRender:
                renderer = QgsGraduatedSymbolRenderer(field, ranges)
            else:
                simb1 = symbol.clone()
                simb2 = symbol.clone()
                simb3 = symbol.clone()
                simb4 = symbol.clone()
                simb5 = symbol.clone()
                simb1.setColor(QColor(0,0,255))
                simb2.setColor(QColor(0,255,255))
                simb3.setColor(QColor(0,255,0))
                simb4.setColor(QColor(255,255,0))
                simb5.setColor(QColor(165,0,0))
                ranges = []
                if "Pressure" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 20, simb1, "<20"))
                    ranges.append(QgsRendererRange(20, 30, simb2, "20-30"))
                    ranges.append(QgsRendererRange(30, 40, simb3, "30-40"))
                    ranges.append(QgsRendererRange(40, 50, simb4, "40-50"))
                    ranges.append(QgsRendererRange(50, 10000, simb5, ">50"))
                elif "Node_Head" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 20, simb1, "<20"))
                    ranges.append(QgsRendererRange(20, 40, simb2, "20-40"))
                    ranges.append(QgsRendererRange(40, 60, simb3, "40-60"))
                    ranges.append(QgsRendererRange(60, 80, simb4, "60-80"))
                    ranges.append(QgsRendererRange(80, 10000, simb5, ">80"))
                elif "Demand" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 5, simb1, "<5"))
                    ranges.append(QgsRendererRange(5, 10, simb2, "5-10"))
                    ranges.append(QgsRendererRange(10, 20, simb3, "10-20"))
                    ranges.append(QgsRendererRange(20, 40, simb4, "20-40"))
                    ranges.append(QgsRendererRange(40, 10000, simb5, ">40"))
                elif "Node_Quality" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 0.25, simb1, "<0.25"))
                    ranges.append(QgsRendererRange(0.25, 0.5, simb2, "0.25-0.5"))
                    ranges.append(QgsRendererRange(0.5, 0.75, simb3, "0.5-0.75"))
                    ranges.append(QgsRendererRange(0.75, 1, simb4, "0.75-1"))
                    ranges.append(QgsRendererRange(1, 10000, simb5, ">1"))
                elif "Flow" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 10, simb1, "<10"))
                    ranges.append(QgsRendererRange(10,20, simb2, "10-20"))
                    ranges.append(QgsRendererRange(20, 50, simb3, "20-50"))
                    ranges.append(QgsRendererRange(50, 100, simb4, "50-100"))
                    ranges.append(QgsRendererRange(100, 10000, simb5, ">100"))
                elif "Velocity" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 0.1, simb1, "<0.1"))
                    ranges.append(QgsRendererRange(0.1, 0.5, simb2, "0.1-0.5"))
                    ranges.append(QgsRendererRange(0.5, 1, simb3, "0.5-1"))
                    ranges.append(QgsRendererRange(1, 2, simb4, "1-2"))
                    ranges.append(QgsRendererRange(2, 10000, simb5, ">2"))
                elif "HeadLoss" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 0.1, simb1, "<0.1"))
                    ranges.append(QgsRendererRange(0.1, 0.5, simb2, "0.1-0.5"))
                    ranges.append(QgsRendererRange(0.5, 1, simb3, "0.5-1"))
                    ranges.append(QgsRendererRange(1, 5, simb4, "1-5"))
                    ranges.append(QgsRendererRange(5, 10000, simb5, ">5"))
                elif "Link_Quality" in nameLayer:
                    ranges.append(QgsRendererRange(-10000, 0.25, simb1, "<0.25"))
                    ranges.append(QgsRendererRange(0.25, 0.5, simb2, "0.25-0.5"))
                    ranges.append(QgsRendererRange(0.5, 0.75, simb3, "0.5-0.75"))
                    ranges.append(QgsRendererRange(0.75, 1, simb4, "0.75-1"))
                    ranges.append(QgsRendererRange(1, 10000, simb5, ">1"))
                else:
                    mode= QgsGraduatedSymbolRenderer.EqualInterval #Quantile
                    classes = 5
                    colorRamp = QgsVectorGradientColorRamp.create({'color1':'0,0,255,255', 'color2':'255,0,0,255','stops':'0.25;0,255,255,255:0.50;0,255,0,255:0.75;255,255,0,255'})
                    self.iface.setActiveLayer(layer)
                    renderer = QgsGraduatedSymbolRenderer.createRenderer( layer, field, classes, mode, symbol, colorRamp )
                    myFormat = renderer.labelFormat()
                    myFormat.setPrecision(2)
                    myFormat.setTrimTrailingZeroes(True)
                    renderer.setLabelFormat(myFormat, True)
                
                if len(ranges)>0:
                    renderer = QgsGraduatedSymbolRenderer(field, ranges)
        else:
            renderer.setClassAttribute(field)
        
        layer.setRenderer(renderer)
        layer.triggerRepaint()

    def writeScenario(self, scenario, labels, comments):
        filePath = os.path.join(os.path.join(self.ProjectDirectory, "Results"), self.NetworkName + "_" + scenario + ".sce")
        f = open(filePath, "w+")
        QGISRedUtils().writeFile(f, "[TimeLabels]"+ '\n')
        lab =""
        for label in labels:
            lab= lab + label + ";"
        lab = lab.strip(';')
        QGISRedUtils().writeFile(f, lab + '\n')
        QGISRedUtils().writeFile(f, "[Comments]"+ '\n')
        QGISRedUtils().writeFile(f, comments + '\n')
        f.close()

    def readSavedScenarios(self):
        resultPath = os.path.join(self.ProjectDirectory, "Results")
        if not os.path.exists(resultPath):
            return
        files = os.listdir(resultPath)
        for file in files: #only names
            if ".sce" in file and not "_Base" in file:
                f= open(os.path.join(resultPath,file), "r")
                nameSc = file.replace(self.NetworkName + "_", "").replace(".sce", "")
                isLabel=False
                isComments = False
                comments=""
                for line in f:
                    if "[TimeLabels]" in line:
                        isLabel = True
                        continue
                    if "[Comments]" in line:
                        isComments = True
                        continue
                    if isLabel:
                        self.LabelResults[nameSc] = line.strip("\r\n").split(';')
                        isLabel=False
                    if isComments:
                        comments = comments + line.strip() + "\n"
                
                comments = comments.strip("\n").strip().strip("\n")
                self.IndexTime[nameSc]=0
                self.Comments[nameSc] = comments
                self.cbScenarios.addItem(nameSc)
                f.close()

    """Clicked events"""
    def linksChanged(self):
        if self.Computing:
            return
        self.cbFlowDirections.setVisible(False)
        if not self.validationsOpenResult():
            return
        result = ""
        if self.cbLinks.currentIndex()==1:
            result= "Flow"
            self.cbFlowDirections.setVisible(True)
        if self.cbLinks.currentIndex()==2:
            result= "Velocity"
        if self.cbLinks.currentIndex()==3:
            result = "HeadLoss"
        if self.cbLinks.currentIndex()==4:
            result= "Quality"
        
        self.setLinksLayersNames()
        self.removeResults(None)
        self.LabelsToOpRe =[]
        if not self.cbLinks.currentIndex()==0:
            self.LabelsToOpRe.append("Link_" + result)
            self.Variables= result +"_Link"
            self.saveCurrentRender()
            self.openResult()

    def nodesChanged(self):
        if self.Computing:
            return
        if not self.validationsOpenResult():
            return
        result = self.cbNodes.currentText()
        result = ""
        if self.cbNodes.currentIndex()==1:
            result= "Pressure"
        if self.cbNodes.currentIndex()==2:
            result= "Head"
        if self.cbNodes.currentIndex()==3:
            result = "Demand"
        if self.cbNodes.currentIndex()==4:
            result= "Quality"
        
        self.setNodesLayersNames()
        self.removeResults(None)
        self.LabelsToOpRe =[]
        if not self.cbNodes.currentIndex()==0:
            self.LabelsToOpRe.append("Node_" + result)
            self.Variables= result +"_Node"
            self.saveCurrentRender()
            self.openResult()

    def nodeLabelsClicked(self):
        self.setNodesLayersNames()
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        layers = [tree_layer.layer() for tree_layer in QgsProject.instance().layerTreeRoot().findLayers()]
        for nameLayer in self.LabelsToOpRe:
            for layer in layers:
                if str(layer.dataProvider().dataSourceUri().split("|")[0]).replace("/","\\")== os.path.join(resultPath, self.NetworkName + "_" + self.Scenario + "_" + nameLayer + ".shp").replace("/","\\"):
                    if self.cbNodeLabels.isChecked():
                        self.setLayerLabels(layer,"T" + str(self.cbTimes.currentIndex()))
                    else:
                        layer.setLabelsEnabled(False)
                        layer.triggerRepaint()

    def linkLabelsClicked(self):
        self.setLinksLayersNames()
        resultPath= os.path.join(self.ProjectDirectory, "Results")
        layers = [tree_layer.layer() for tree_layer in QgsProject.instance().layerTreeRoot().findLayers()]
        for nameLayer in self.LabelsToOpRe:
            for layer in layers:
                if str(layer.dataProvider().dataSourceUri().split("|")[0]).replace("/","\\")== os.path.join(resultPath, self.NetworkName + "_" + self.Scenario + "_" + nameLayer + ".shp").replace("/","\\"):
                    if self.cbLinkLabels.isChecked():
                        self.setLayerLabels(layer,"T" + str(self.cbTimes.currentIndex()))
                    else:
                        layer.setLabelsEnabled(False)
                        layer.triggerRepaint()

    def flowDirectionsClicked(self):
        if self.cbLinks.currentIndex()==1:
            if not self.validationsOpenResult(True):
                return
            if self.cbLinks.currentIndex()==1:
                self.LabelsToOpRe.append("Link_Flow")
                self.Variables="Flow_Link"
                value = self.cbTimes.currentIndex()
                self.paintIntervalTimeResults(value, False)

    def nextTime(self):
        index = self.cbTimes.currentIndex()
        if self.cbTimes.count()-1 == index:
            self.cbTimes.setCurrentIndex(0)
        else:
            self.cbTimes.setCurrentIndex(index+1)

    def previousTime(self):
        index = self.cbTimes.currentIndex()
        if index==0:
            self.cbTimes.setCurrentIndex(self.cbTimes.count()-1)
        else:
            self.cbTimes.setCurrentIndex(index-1)

    def timeChanged(self):
        if self.Computing:
            return
        self.Scenario = self.cbScenarios.currentText()
        resultPath = os.path.join(os.path.join(self.ProjectDirectory, "Results"),self.NetworkName + "_" + self.Scenario)
        if resultPath is None:
            self.iface.messageBar().pushMessage("Warning", "No scenario results are available", level=1, duration=5)
            return
        
        value = self.cbTimes.currentIndex()
        self.IndexTime[self.cbScenarios.currentText()]=value
        self.setLayersNames()
        self.paintIntervalTimeResults(value)

    def play(self):
        self.btPlay.setEnabled(False)
        for label in self.TimeLabels:
            task1 = QgsTask.fromFunction(u'Visualizate', self.playTask, wait_time=0)
            task1.run()
            QgsApplication.taskManager().addTask(task1)
        
        self.btPlay.setEnabled(True)

    def playTask(self, task, wait_time):
        #self.hsTimes.setValue(self.hsTimes.value() + 1)
        sleep(1)

    def scenarioChanged(self):
        if self.Computing:
            return
        
        currentScenario= self.cbScenarios.currentText()
        self.TimeLabels =self.LabelResults[currentScenario]
        self.Computing = True
        
        self.cbTimes.clear()
        if len(self.TimeLabels)==1:
            self.lbLabel5.setVisible(False)
            self.btLessTime.setVisible(False)
            self.btMoreTime.setVisible(False)
            self.cbTimes.setVisible(False)
            self.cbTimes.addItem("Permanent")
        else:
            self.lbLabel5.setVisible(True)
            self.btLessTime.setVisible(True)
            self.btMoreTime.setVisible(True)
            self.cbTimes.setVisible(True)
            for label in self.TimeLabels:
                self.cbTimes.addItem(label)
            if self.IndexTime.get(currentScenario) is not None:
                self.cbTimes.setCurrentIndex(self.IndexTime[currentScenario])
        self.lbTime.setText(self.TimeLabels[self.IndexTime[currentScenario]])
        self.lbComments.setText(self.Comments[currentScenario])
        self.Computing=False
        
        self.btDeleteScenario.setEnabled(not currentScenario== "Base")
        
        self.Scenario= currentScenario
        self.restoreElementsCb()
        self.Computing = True
        self.setLayersNames()
        if len(self.LabelsToOpRe)==0:
            self.cbLinks.setCurrentIndex(1)
            self.cbFlowDirections.setVisible(True)
            self.cbNodes.setCurrentIndex(1)
            self.IndexTime[currentScenario]=self.cbTimes.currentIndex()
            self.openAllResults()
        self.Computing = False

    """Main methods"""
    def validationsOpenResult(self, restore=False):
        if not self.isCurrentProject():
            return False
        self.Scenario = self.cbScenarios.currentText()
        resultPath = os.path.join(os.path.join(self.ProjectDirectory, "Results"),self.NetworkName + "_" + self.Scenario)
        if resultPath is None:
            self.iface.messageBar().pushMessage("Warning", "No scenario results are available", level=1, duration=5)
            return False
        
        if restore:
            self.restoreElementsCb()
        self.LabelsToOpRe=[]
        return True

    def openAllResults(self):
        resultPath = os.path.join(os.path.join(self.ProjectDirectory, "Results"),self.NetworkName + "_" + self.Scenario)
        if resultPath is None:
            self.iface.messageBar().pushMessage("Warning", "No scenario results are available", level=1, duration=5)
            return

        if not self.setVariablesTimes():
            return
        
        #Process
        self.setLayersNames(True)
        #Task is necessary because after remove layers, DBF files are in use. With the task, the remove process finishs and filer are not in use
        task1 = QgsTask.fromFunction(u'Dismiss this message', self.removeResults, on_finished=self.openAllResultsProcess)
        task1.run()
        QgsApplication.taskManager().addTask(task1)

    def openAllResultsProcess(self, exception=None, result=None):
        self.setLayersNames()
        
        found = True
        for file in self.LabelsToOpRe:
            f = os.path.join(self.ProjectDirectory, "Results", self.NetworkName + "_" + self.Scenario + "_" + file + ".shp")
            if not os.path.exists(f):
                found = False
        if not found:
            #Process
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QGISRedUtils().setCurrentDirectory()
            mydll = WinDLL("GISRed.QGisPlugins.dll")
            mydll.CreateResults.argtypes = (c_char_p, c_char_p, c_char_p, c_char_p, c_char_p, c_char_p)
            mydll.CreateResults.restype = c_char_p
            b = mydll.CreateResults(self.ProjectDirectory.encode('utf-8'), self.NetworkName.encode('utf-8'), self.Scenario.encode('utf-8'), self.Variables.encode('utf-8'), "".encode('utf-8'), "".encode('utf-8'))
            b= "".join(map(chr, b)) #bytes to string
        else:
            b="True"
        
        #Open layers
        self.openLayerResults(self.Scenario)
        value = self.cbTimes.currentIndex()
        self.paintIntervalTimeResults(value, True)
        QApplication.restoreOverrideCursor()
        
        self.iface.actionMapTips().setChecked(True)
        
        #Message
        if b=="True":
            pass# self.iface.messageBar().pushMessage("Information", "Process successfully completed", level=3, duration=5)
        elif b=="False":
            self.iface.messageBar().pushMessage("Warning", "Some issues occurred in the process", level=1, duration=5)
        else:
            self.iface.messageBar().pushMessage("Error", b, level=2, duration=5)

    def openResult(self):
        self.openResultProcess()
        # #Task is necessary because after remove layers, DBF files are in use. With the task, the remove process finishs and filer are not in use
        # task1 = QgsTask.fromFunction(u'Dismiss this message', self.removeResults, on_finished=self.openResultProcess)
        # task1.run()
        # QgsApplication.taskManager().addTask(task1)
        pass

    def openResultProcess(self, exception=None, result=None):
        found = True
        for file in self.LabelsToOpRe:
            f = os.path.join(self.ProjectDirectory, "Results", self.NetworkName + "_" + self.Scenario + "_" + file + ".shp")
            if not os.path.exists(f):
                found = False
        if not found:
            #Process
            QApplication.setOverrideCursor(Qt.WaitCursor)
            QGISRedUtils().setCurrentDirectory()
            mydll = WinDLL("GISRed.QGisPlugins.dll")
            mydll.CreateResults.argtypes = (c_char_p, c_char_p, c_char_p, c_char_p, c_char_p, c_char_p)
            mydll.CreateResults.restype = c_char_p
            b = mydll.CreateResults(self.ProjectDirectory.encode('utf-8'), self.NetworkName.encode('utf-8'), self.Scenario.encode('utf-8'), self.Variables.encode('utf-8'), "".encode('utf-8'), "".encode('utf-8'))
            b= "".join(map(chr, b)) #bytes to string
        else:
            b="True"
        
        #Open layers
        self.openLayerResults(self.Scenario)
        value = self.cbTimes.currentIndex()
        self.paintIntervalTimeResults(value, True)
        QApplication.restoreOverrideCursor()
        
        #Message
        if b=="True":
            pass# self.iface.messageBar().pushMessage("Information", "Process successfully completed", level=3, duration=5)
        elif b=="False":
            self.iface.messageBar().pushMessage("Warning", "Some issues occurred in the process", level=1, duration=5)
        else:
            self.iface.messageBar().pushMessage("Error", b, level=2, duration=5)

    def saveScenario(self):
        if not self.isCurrentProject():
            return False
        #Validations
        isBaseScenario = self.cbScenarios.currentText() == "Base"
        if not isBaseScenario:
            self.iface.messageBar().pushMessage("Warning", "Only 'Base' scenario could be saved", level=1, duration=5)
            return
        newScenario = self.tbScenarioName.text().strip()
        if newScenario=="":
            self.iface.messageBar().pushMessage("Warning", "Scenario name is not valid", level=1, duration=5)
            return
        for i in range(self.cbScenarios.count()):
            if self.cbScenarios.itemText(i).lower()==newScenario.lower():
                self.iface.messageBar().pushMessage("Warning", "Scenario name is already used", level=1, duration=5)
                return
        
        #Save options
        resultPath = os.path.join(self.ProjectDirectory, "Results")
        try:
            copyfile(os.path.join(resultPath,self.NetworkName + "_Base"), os.path.join(resultPath,self.NetworkName + "_" + newScenario))#Binary
            files = os.listdir(resultPath)
            for file in files: #only names
                if self.NetworkName + "_Base_Link" in file or self.NetworkName + "_Base_Node" in file:
                    newName= file.replace("_Base_", "_" + newScenario + "_")
                    copyfile(os.path.join(resultPath,file), os.path.join(resultPath,newName))
            
            self.LabelResults[newScenario] = self.TimeLabels
            self.IndexTime[newScenario]=self.cbTimes.currentIndex()
            self.Comments[newScenario] = self.tbComments.toPlainText().strip().strip("\n")
            self.writeScenario(newScenario, self.TimeLabels, self.Comments[newScenario])
        except:
            self.iface.messageBar().pushMessage("Error", "Scenario could not be saved", level=2, duration=5)
            return
        self.Scenario="Base"
        self.saveCurrentRender(True)
        
        self.cbScenarios.addItem(newScenario)
        self.cbScenarios.setCurrentIndex(self.cbScenarios.count()-1)
        self.tbScenarioName.setText("")

    def deleteScenario(self):
        self.Scenario = self.cbScenarios.currentText()
        
        #Process
        self.setLayersNames(True)
        #Task is necessary because after remove layers, DBF files are in use. With the task, the remove process finishs and filer are not in use
        task1 = QgsTask.fromFunction(u'Dismiss this message', self.removeResults, on_finished=self.deleteScenarioProcess, wait_time=0)
        task1.run()
        QgsApplication.taskManager().addTask(task1)

    def deleteScenarioProcess(self, exception=None, result=None):
        #Delete Group
        resultGroup = self.getResultGroup()
        dataGroup = resultGroup.findGroup(self.Scenario)
        if dataGroup is not None:
            resultGroup.removeChildNode(dataGroup)
        #Delete files
        resultPath = os.path.join(self.ProjectDirectory, "Results")
        files = os.listdir(resultPath)
        for file in files: #only names
            if self.NetworkName + "_" + self.Scenario in file:
                try:
                    os.remove(os.path.join(resultPath, file))
                except:
                    pass
        
        #Delete from combobox
        self.cbScenarios.removeItem(self.cbScenarios.currentIndex())
        self.cbScenarios.setCurrentIndex(self.cbScenarios.count()-1)