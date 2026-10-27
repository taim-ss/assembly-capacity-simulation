"""SYNTHETIC v2 experiment presets. Director's manifests override run counts."""
import copy
import json


def add_experiments(exps, template, ids, args, tag, code, ident):
    presets = {
        "ValidationSweep": {"studyLabel": '"validation"', **{"cap"+s:"50" for s in ["Kitting","Assembly","Test","Quality","Handover"]}, "meanInterarrival":"5.0540201005"},
        "SteadyStateSweep": {"studyLabel": '"steady"', "meanInterarrival":"5.0540201005", "scenarioOrders":"5000", **dict(zip(["cap"+s for s in ["Kitting","Assembly","Test","Quality","Handover"]],map(str,[2,5,5,3,1])))},
        "ReworkSweep": {"studyLabel": '"rework"', "reworkProbability":"0.1"},
        "ComponentSweep": {"studyLabel": '"component"', "componentMode":"1", "componentMeanInterarrival":"5.0540201005"},
        "InputModeSweep": {"studyLabel": '"input"', "inputMode":"1"},
        "MMCVerification": {"verificationMode":"true", "verificationServers":"3", "verificationMeanService":"1.0", "meanInterarrival":"0.47619047619047616", "capKitting":"3", "scenarioOrders":"10000", "scenarioIndex":"0"},
    }
    for name, overrides in presets.items():
        exp=copy.deepcopy(template)
        exp.find("Id").text=ident(__import__('xml.etree.ElementTree',fromlist=['Element']).Element("x")).findtext("Id")
        exp.find("Name").text=name
        for key,value in overrides.items():
            node=next(n for n in exp.findall("RangeVariationParamValue") if n.findtext("Id")==ids[key])
            for child in list(node):
                if child.tag!="Id":node.remove(child)
            tag(node,"Type","FIXED");code(node,"Expression",value)
        tag(exp,"BypassInitialScreen","true")
        exps.append(exp)
