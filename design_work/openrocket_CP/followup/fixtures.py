"""Derive the three ORK external geometries from the frozen half-inch design."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import os
import xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
out=Path(os.environ.get('CP_WORK',root/'work'))/'handover';out.mkdir(parents=True,exist_ok=True)
for part in ('forebody','finless','finned'):
    with ZipFile(root/'inputs/iris/preferred.ork') as z: xml=ET.fromstring(z.read('rocket.ork'))
    stages=xml.find('rocket/subcomponents');sustainer,booster=stages.findall('stage');stages.remove(booster)
    # Static fixtures discard flight and motor assignments tied to the removed stage.
    xml.remove(xml.find('simulations'))
    rocket=xml.find('rocket')
    for config in rocket.findall('motorconfiguration'):rocket.remove(config)
    for parent in sustainer.iter():
        for mount in parent.findall('motormount'):parent.remove(mount)
    pieces=sustainer.find('subcomponents')
    if part=='forebody':
        for child in list(pieces)[2:]:pieces.remove(child)
        tube=pieces.find('bodytube/subcomponents')
        for pods in tube.findall('podset'):tube.remove(pods)
    if part=='finless':
        for parent in pieces.iter('subcomponents'):
            for fins in parent.findall('trapezoidfinset'):parent.remove(fins)
    with ZipFile(out/(part+'.ork'),'w',compression=ZIP_DEFLATED) as z:z.writestr('rocket.ork',ET.tostring(xml,encoding='utf-8'))
