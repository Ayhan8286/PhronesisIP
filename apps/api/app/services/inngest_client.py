import os
import inngest

# Create the Inngest client
inngest_client = inngest.Inngest(
    app_id="patentiq-backend",
    is_production=os.getenv("APP_ENV") == "production",
)
