import os
import inngest

# Create the Inngest client
# We only enforce production mode (and signing requirement) if a key is present
is_prod = os.getenv("APP_ENV") == "production"
signing_key = os.getenv("INNGEST_SIGNING_KEY")

inngest_client = inngest.Inngest(
    app_id="patentiq-backend",
    is_production=is_prod and signing_key is not None,
)
