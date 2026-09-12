from app.profile import WorkflowProfile
from noark5_workflow.operations import (
    BuildNoark5DepotReportOperation,
    ComposeNoark5ViewsOperation,
    AnalyseArkivstrukturOperation,
    AnalyseNoark5CoreOperation,
    AnalyseNoark5U1Operation,
    DiasPackageOperation,
    MetadataInventoryOperation,
    RunNoark5XpathRegressionOperation,
    RunNoark5XpathTestsOperation,
    ValidateXmlSchemaOperation,
)


NOARK5_CATEGORIES = (
    "Pipeline",
    "Integritet",
    "Sikkerhet",
    "Innhold",
    "Systemspesifikt",
    "Kompatibilitet",
    "Rapport",
    "Metadata",
    "SIP/AIC-Pakking",
)

NOARK5_CATEGORY_COLORS = {
    "Pipeline": "#4f8ef7",
    "Integritet": "#4f8ef7",
    "Sikkerhet": "#e05252",
    "Innhold": "#f0c040",
    "Systemspesifikt": "#4f8ef7",
    "Kompatibilitet": "#4f8ef7",
    "Rapport": "#f97316",
    "Metadata": "#a78bfa",
    "SIP/AIC-Pakking": "#4f8ef7",
}


NOARK5_PROFILE = WorkflowProfile(
    profile_id="noark5",
    name="Noark 5",
    description="Analyse, validering, rapportering og pakking av Noark 5-uttrekk.",
    categories=NOARK5_CATEGORIES,
    category_colors=NOARK5_CATEGORY_COLORS,
    operation_factories=(
        MetadataInventoryOperation,
        AnalyseArkivstrukturOperation,
        AnalyseNoark5CoreOperation,
        AnalyseNoark5U1Operation,
        RunNoark5XpathTestsOperation,
            RunNoark5XpathRegressionOperation,
        ComposeNoark5ViewsOperation,
        BuildNoark5DepotReportOperation,
        ValidateXmlSchemaOperation,
        DiasPackageOperation,
    ),
)
