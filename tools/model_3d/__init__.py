"""Post-processing package that adds a 3D animation layer to the generated
P3_Assembly_Flow.alp without touching tools/build_model.py or any logic block.

Schema notes (verified 2026-10-24 against the installed AnyLogic 8.9.10 PLE
jars, see docs/3d-user-guide.md "Where the schema facts came from"):
  - Element property names were read from the constant pool of
    com.anylogic.objectmodel.jar classes (OMRectangle, OMOval, OMText,
    OMFunction, OMCamera3D, OMViewArea, OMAbstractAnimationLayerElement,
    OMSimulationExperiment, OMExperiment) because this AnyLogic edition ships
    no .xsd. Tag name == bean property name (confirmed against the
    already-present <Text><FillColor>... elements build_model.py itself
    writes into model/P3_Assembly_Flow.alp).
  - Runtime PML API (queueSize(), size(), busy(), utilization()) was read
    from the shipped Javadoc under
    plugins/com.anylogic.process_modeling_library_*/lib/doc/.
  - Everything here is therefore a *static, schema-informed* best effort,
    not an AnyLogic-verified fact. The model must still be opened in the
    AnyLogic editor once before Taim trusts it (see docs/3d-user-guide.md).
"""
