from app.core.llm import chat

PITCH_SYSTEM_PROMPT = """You are an expert insurance sales coach in India.
Generate a personalized sales pitch for an insurance advisor to use with their client.
Be conversational, empathetic, and specific to the client's profile.
Focus on real needs, not just products. Avoid jargon.
Format: Opening → Key Need → Recommended Solution → Call to Action."""

OBJECTION_SYSTEM_PROMPT = """You are an expert insurance sales coach in India.
Help an insurance advisor respond to a client objection.
Be empathetic, acknowledge the concern, then reframe it positively.
Keep the response concise — 3 to 5 sentences the advisor can say out loud.
Do not be pushy. Focus on the client's benefit."""

COMMON_OBJECTIONS = [
    "premium is too high",
    "I already have insurance",
    "I will think about it",
    "I don't trust insurance companies",
    "I am young and healthy, I don't need it",
    "I don't have time right now",
    "my employer already covers me",
]


async def generate_pitch(client_profile: dict) -> str:
    user_message = f"""
Generate a sales pitch for the following client:

- Name: {client_profile.get('name')}
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Family Size: {client_profile.get('family_size')}
- Risk Appetite: {client_profile.get('risk_appetite')}
- Goals: {client_profile.get('goals')}
- Existing Policies: {client_profile.get('existing_policies', 'None')}

Create a natural, personalized pitch the advisor can use in a conversation.
"""
    return await chat(PITCH_SYSTEM_PROMPT, user_message, trace_name="pitch_generator")


async def handle_objection(objection: str, client_profile: dict) -> str:
    user_message = f"""
Client objection: "{objection}"

Client context:
- Age: {client_profile.get('age')}
- Annual Income: ₹{client_profile.get('income', 0):,.0f}
- Family Size: {client_profile.get('family_size')}
- Goals: {client_profile.get('goals')}
- Existing Policies: {client_profile.get('existing_policies', 'None')}

Write a short, empathetic response the advisor can say out loud to address this objection.
"""
    return await chat(OBJECTION_SYSTEM_PROMPT, user_message, trace_name="objection_handler")
