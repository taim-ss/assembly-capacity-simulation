"""SYNTHETIC AnyLogic XML utilities recovered from the interrupted generator."""
import xml.etree.ElementTree as ET
PKG="p3_synthetic_assembly"
PML="com.anylogic.libraries.processmodeling"
serial = 1800000000000


def tag(parent, name, value=None, **attrs):
    e = ET.SubElement(parent, name, attrs)
    if value is not None:
        e.text = str(value)
    return e


def ident(e, name=None, x=None, y=None):
    global serial
    serial += 1
    tag(e, "Id", serial)
    if name is not None:
        tag(e, "Name", name)
    if x is not None:
        tag(e, "X", x)
        tag(e, "Y", y)
        l = tag(e, "Label")
        tag(l, "X", 0)
        tag(l, "Y", -20)
        for k, v in [("PublicFlag", "false"), ("PresentationFlag", "true"), ("ShowLabel", "true")]:
            tag(e, k, v)
    return e


def code(parent, name, value, unit=None, classname=None):
    e = tag(parent, name, Class=classname or ("CodeUnitValue" if unit else "CodeValue"))
    tag(e, "Code", value)
    if unit:
        tag(e, "Unit", unit, Class="TimeUnits")
    return e


def variable(parent, name, typ, initial, parameter=False):
    e = ident(tag(parent, "Variable", Class="Parameter" if parameter else "PlainVariable"), name, 30, 500)
    if parameter:
        p = tag(e, "Properties", SaveInSnapshot="true", ModificatorType="STATIC")
        tag(p, "Type", typ)
        tag(p, "UnitType", "NONE")
        tag(p, "SdArray", "false")
        code(p, "DefaultValue", initial)
        editor = ident(tag(p, "ParameterEditor"))
        tag(editor, "EditorContolType", "TEXT_BOX")
        tag(editor, "MinSliderValue", 0)
        tag(editor, "MaxSliderValue", 100)
        tag(editor, "DelimeterType", "NO_DELIMETER")
    else:
        p = tag(e, "Properties", SaveInSnapshot="true", Constant="false", AccessType="public", StaticVariable="false")
        tag(p, "Type", typ)
        code(p, "InitialValue", initial)
    return e


def agent(parent, name):
    e = ident(tag(parent, "ActiveObjectClass"), name)
    tag(e, "Generic", "false")
    generic=ident(tag(e,"GenericParameter"),"T")
    code(generic,"GenericParameterValue","T extends Agent")
    tag(generic,"GenericParameterLabel","Generic parameter:")
    tag(e, "FlowChartsUsage", "ENTITY")
    tag(e, "SamplesToKeep", 100)
    tag(e, "LimitNumberOfArrayElements", "false")
    tag(e, "ElementsLimitValue", 100)
    tag(e, "MakeDefaultViewArea", "true")
    for k,v in [("SceneGridColor",None),("SceneBackgroundColor",-4144960),("EnvironmentResourceRef",None),("EnvironmentType","NONE"),("EnvironmentRotationX",0),("EnvironmentRotationY",0),("EnvironmentRotationZ",0),("EnvironmentIntensity",1)]:tag(e,k,v)
    props = tag(e, "AgentProperties")
    tag(props, "EnvironmentDefinesInitialLocation", "true")
    tag(props, "RotateAnimationTowardsMovement", "false")
    tag(props,"RotateAnimationVertically","false")
    code(props,"VelocityCode","10","MPS").find("Unit").set("Class","SpeedUnits")
    tag(props,"MessageType","Object")
    for n in ["PhysicalLength","PhysicalWidth","PhysicalHeight"]:
        code(props,n,"1","METER").find("Unit").set("Class","LengthUnits")
    env = tag(e, "EnvironmentProperties")
    tag(env, "EnableSteps", "false")
    code(env,"StepDurationCode","1.0","HOUR")
    tag(env, "SpaceType", "CONTINUOUS")
    tag(env, "WidthCode", 1200)
    tag(env, "HeightCode", 600)
    for k,v in [("ZHeightCode",0),("ColumnsCountCode",100),("RowsCountCode",100),("NeigborhoodType","MOORE"),("LayoutType","RANDOM"),("NetworkType","USER_DEF"),("ConnectionsPerAgentCode",2),("ConnectionsRangeCode",50),("NeighborLinkFractionCode",0.95),("MCode",10),("LineStyle","SOLID"),("LineWidth",1),("LineColor",-16777216),("LineZOrder","UNDER_AGENTS"),("LineArrow","NONE"),("LineArrowPosition","END")]:tag(env,k,v)
    datasets=tag(e,"DatasetsCreationProperties");tag(datasets,"AutoCreate","true");ident(datasets)
    tag(datasets,"OccurrenceAtTime","true");tag(datasets,"OccurrenceDate",1772409600000)
    code(datasets,"OccurrenceTime","0","HOUR");code(datasets,"RecurrenceCode","1","HOUR")
    ruler=ident(tag(e,"ScaleRuler"),"scale",0,-150)
    for k,v in [("DrawMode","SHAPE_DRAW_2D3D"),("Length",100),("Rotation",0),("ScaleType","BASED_ON_LENGTH"),("ModelLength",10),("LengthUnits","METER"),("Scale",10),("InheritedFromParentAgentType","true")]:tag(ruler,k,v)
    presentation=tag(e,"Presentation");level=ident(tag(presentation,"Level"),"level",0,0)
    for k,v in [("DrawMode","SHAPE_DRAW_2D3D"),("Z",0),("LevelVisibility","DIM_NON_CURRENT")]:tag(level,k,v)
    tag(level,"Presentation");tag(e,"CurrentLevel",level.findtext("Id"))
    agent_links=tag(e,"AgentLinks");link=ident(tag(agent_links,"AgentLink"),"connections",50,-50)
    tag(e,"ConnectionsId",link.findtext("Id"))
    for k,v in [("HandleReceiveInConnections","false"),("AgentLinkType","COLLECTION_OF_LINKS"),("AgentLinkBidirectional","true"),("MessageType","Object"),("LineStyle","SOLID"),("LineWidth",1),("LineColor",-16777216),("LineZOrder","UNDER_AGENTS"),("LineArrow","NONE"),("LineArrowPosition","END")]:tag(link,k,v)
    return e


blocks = {}
links = []


def block(parent, name, typ, x, y, settings):
    e = ident(tag(parent, "EmbeddedObject"), name, x, y)
    a = tag(e, "ActiveObjectClass")
    tag(a, "PackageName", PML)
    tag(a, "ClassName", typ)
    ps = tag(e, "Parameters")
    for n, value in settings.items():
        p = tag(ps, "Parameter")
        tag(p, "Name", n)
        if isinstance(value, tuple):
            code(p, "Value", value[0], value[1])
        else:
            code(p, "Value", value)
    tag(e, "ReplicationFlag", "false")
    code(e, "Replication", "100")
    tag(e, "CollectionType", "ARRAY_LIST_BASED")
    tag(e, "InitialLocationType", "XYZ")
    code(e, "ColumnCode", "0")
    code(e, "RowCode", "0")
    code(e, "LocationNameCode", '""')
    tag(e, "InitializationType", "SPECIFIED_NUMBER")
    blocks[name] = (typ, x, y)
    return e


def connect(parent, source, target, sport="out", tport="in"):
    links.append((source,target,sport,tport))


def write_connection(parent, source, target, sport="out", tport="in"):
    e = ident(tag(parent, "Connector"), f"link{len(parent)}", 0, 0)
    # Stored connector orientation is arbitrary; these refs explicitly identify ports.
    for prefix, name, port in [("Source", source, sport), ("Target", target, tport)]:
        ref = tag(e, prefix + "EmbeddedObjectReference")
        for k, v in [("PackageName", PKG), ("ClassName", "Main"), ("ItemName", name)]:
            tag(ref, k, v)
        ref = tag(e, prefix + "ConnectableItemReference")
        for k, v in [("PackageName", PML), ("ClassName", blocks[name][0]), ("ItemName", port)]:
            tag(ref, k, v)
    pts = tag(e, "Points")
    for name in [source, target]:
        p = tag(pts, "Point")
        tag(p, "X", blocks[name][1])
        tag(p, "Y", blocks[name][2])


