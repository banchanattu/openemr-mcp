# Create Appointment

I have found in the swagger documentation that appointment can be created with

There is a POST operation for /api/patient/{pid}/appointment

The body expected is a JSON with follwoing format

with example values 

{
  "pc_catid": "5",
  "pc_title": "Office Visit",
  "pc_duration": "900",
  "pc_hometext": "Test",
  "pc_apptstatus": "-",
  "pc_eventDate": "2018-10-19",
  "pc_startTime": "09:00",
  "pc_facility": "9",
  "pc_billing_location": "10",
  "pc_aid": "1"
}

The detailed schema is 
{
pc_catid*	string
The category of the appointment.

pc_title*	string
The title of the appointment.

pc_duration*	string
The duration of the appointment.

pc_hometext*	string
Comments for the appointment.

pc_apptstatus*	[...]
pc_eventDate*	string
The date of the appointment.

pc_startTime*	string
The time of the appointment.

pc_facility*	string
The facility id of the appointment.

pc_billing_location*	string
The billinag location id of the appointment.

pc_aid	string
The provider id for the appointment.

}
example: OrderedMap { "pc_catid": "5", "pc_title": "Office Visit", "pc_duration": "900", "pc_hometext": "Test", "pc_apptstatus": "-", "pc_eventDate": "2018-10-19", "pc_startTime": "09:00", "pc_facility": "9", "pc_billing_location": "10", "pc_aid": "1" }


Response 
	
Standard Response

Media type

application/json
Controls Accept header.
Example Value
Schema
{
  "validationErrors": {},
  "error_description": {},
  "data": {}
}
No links
400	
Bad Request

Media type

application/json
Example Value
Schema
{
  "validationErrors": {
    "_id": "The search field argument was invalid, improperly formatted, or could not be parsed.  Inner message: UUID columns must be a valid UUID string"
  }
}
No links
401	
Unauthorized

Media type

application/json
Example Value
Schema
{
  "error": "access_denied",
  "error_description": "The resource owner or authorization server denied the request.",
  "hint": "Missing \"Authorization\" header",
  "message": "The resource owner or authorization server denied the request."
}
No links

Can you prepare a plan to add this as a @mcp tool function.

Lookt at thee current patgter for patient creation.

for more inrmation ../openemr contains the server project 
Update this doce with your plan. I Will reivew and approve it.

## Proposed plan

This should follow the same structure as `openemr_patient_create`:

1. Add request and response schemas in `src/openemr_mcp/schemas.py`
2. Add a tool wrapper in `src/openemr_mcp/tools/appointments.py`
3. Add the API implementation in `src/openemr_mcp/repositories/fhir_api.py`
4. Register the tool in both `src/openemr_mcp/server.py` and `src/openemr_mcp/http_server.py`
5. Add tests in `tests/test_tools.py`

## Endpoint and repo notes

I verified in `../openemr` that the standard REST route exists:

- `POST /api/patient/:pid/appointment` in `../openemr/apis/routes/_rest_routes_standard.inc.php`
- Swagger entry in `../openemr/swagger/openemr-api.yaml`

This means the MCP tool should target the standard REST API, not FHIR, for appointment creation.

## Detailed implementation plan

### 1. Add schema models

Add a create payload model, separate from the existing read model:

- `AppointmentCreate`
- `AppointmentCreateResult` or `AppointmentCreateResponse`

Suggested request fields:

- `patient_id: str`
- `pc_catid: str`
- `pc_title: str`
- `pc_duration: str`
- `pc_hometext: str`
- `pc_apptstatus: str`
- `pc_eventDate: str`
- `pc_startTime: str`
- `pc_facility: str`
- `pc_billing_location: str`
- `pc_aid: str | None = None`

Suggested response shape:

- `appointment_id: str | None`
- `patient_id: str`
- `status: str`
- `message: str | None = None`
- `raw_data: dict | None = None`

Reasoning:

- The existing `Appointment` model is a normalized read model for listing.
- Create should keep the OpenEMR field names because they map directly to the REST payload.
- The create response should be tolerant of whatever the OpenEMR REST endpoint actually returns in `data`.

### 2. Add input normalization and validation in `tools/appointments.py`

Add a new function similar to `run_create_patient`:

- `run_create_appointment(...) -> AppointmentCreateResult`

Add small validation helpers, similar to the patient tool:

- validate `patient_id` is present
- validate required string fields are non-empty
- validate `pc_eventDate` is `YYYY-MM-DD`
- validate `pc_startTime` is `HH:MM` or `HH:MM:SS`
- optionally normalize `pc_apptstatus` and reject empty values

Mock mode behavior:

- create a deterministic mock appointment id such as `a1501`
- append a mock appointment to `MOCK_APPOINTMENTS`
- map the create payload into the existing normalized `Appointment` list structure
- return an `AppointmentCreateResult`

This matches the current pattern where patient create works in both mock and API modes.

### 3. Add REST repository implementation in `repositories/fhir_api.py`

Despite the file name, this repo already contains non-FHIR REST logic for appointments via `http_client.get_rest(...)`.
Add a companion function:

- `create_appointment_api(payload: AppointmentCreate, http_client: Any) -> AppointmentCreateResult`

Implementation shape:

- normalize `patient_id` from `p001` to numeric `1` when possible
- call `http_client.post_rest(f"patient/{pid_int}/appointment", json_body)`
- pass the payload using the OpenEMR field names exactly as documented
- inspect the returned body and extract:
  - created appointment id if present
  - returned status/message if present
  - fallback to raw `data` when the structure is not stable

Error handling:

- if the API returns an invalid body, raise `ToolError`
- preserve validation and transport failures from the HTTP client

### 4. Register the MCP tool

Add a new tool in `src/openemr_mcp/server.py`:

- name: `openemr_appointment_create`
- description: create a new appointment for an existing patient

Input schema should expose the required OpenEMR fields explicitly, the same way `openemr_patient_create` does.

Add dispatch logic in `_dispatch(...)`:

- import `run_create_appointment`
- forward all fields explicitly

Add the matching FastMCP HTTP tool in `src/openemr_mcp/http_server.py`.

### 5. Add tests

Add unit tests covering:

- mock appointment create succeeds
- created mock appointment is visible through `run_appointment_list`
- invalid date is rejected
- missing required field is rejected
- API repository uses the correct REST path
- API repository sends the exact OpenEMR field names in the POST body
- API repository correctly parses a minimal successful response

This should mirror the level of coverage already present for patient create.

## Design decisions that need approval

### A. MCP tool field names

Option 1:

- expose raw OpenEMR field names like `pc_catid`, `pc_eventDate`, `pc_startTime`

Option 2:

- expose friendlier MCP names like `category_id`, `event_date`, `start_time`
- translate them to OpenEMR names inside the repository layer

Recommendation:

- use friendlier MCP names in the public tool interface
- keep `AppointmentCreate` as the normalized MCP input model
- translate to OpenEMR REST field names only inside `create_appointment_api(...)`

Reason:

- this makes the MCP tool easier for model callers to use
- it avoids leaking OpenEMR internal naming into the MCP contract

If you want strict consistency with the Swagger payload and faster implementation, we can instead expose the raw `pc_*` names directly.

### B. Response contract

Option 1:

- return a minimal create result with id/status/message

Option 2:

- return a normalized `Appointment` object plus status metadata

Recommendation:

- return normalized appointment details plus a small status wrapper if the API returns enough information
- otherwise return a minimal create result and keep the raw response available for debugging

### C. File placement

The repo currently places REST and FHIR API code together in `repositories/fhir_api.py`.

Recommendation:

- keep appointment create there for consistency with current code
- do not introduce a new repository file in this change

## Proposed concrete file changes

- `src/openemr_mcp/schemas.py`
  - add appointment create request/response models
- `src/openemr_mcp/tools/appointments.py`
  - add validation helpers
  - add mock create support
  - add `run_create_appointment(...)`
- `src/openemr_mcp/repositories/fhir_api.py`
  - add `create_appointment_api(...)`
- `src/openemr_mcp/server.py`
  - add tool schema
  - add dispatch case
- `src/openemr_mcp/http_server.py`
  - add FastMCP tool wrapper
- `tests/test_tools.py`
  - add mock and API unit tests

## Suggested implementation order

1. Approve the public tool shape
2. Add schemas
3. Implement mock-mode tool path
4. Implement REST API path
5. Register the MCP tool
6. Add tests
7. Run the appointment and patient smoke tests

## My recommendation

I recommend we expose a clean MCP-facing tool like:

- `openemr_appointment_create`
- inputs:
  - `patient_id`
  - `category_id`
  - `title`
  - `duration`
  - `comments`
  - `appointment_status`
  - `event_date`
  - `start_time`
  - `facility_id`
  - `billing_location_id`
  - `provider_id` optional

and translate those to the raw OpenEMR `pc_*` fields inside the repository layer.

That is the cleanest long-term contract, even though it is a slightly larger change than passing the Swagger field names through directly.
