<p align="center">
  <a href="https://asok-framework.com/">
    <img src="https://raw.githubusercontent.com/codewithmpia/asok-auth-providers/main/asok_auth_providers/assets/asok.svg" alt="Asok Logo" width="60" height="60" />
  </a>
  <span style="font-size: 32px; font-weight: bold; margin: 0 15px; position: relative; bottom: 15px; color: #6B7280;">+</span>
  <a href="https://github.com/codewithmpia/asok-auth-providers">
    <img src="https://raw.githubusercontent.com/codewithmpia/asok-auth-providers/main/asok_auth_providers/assets/auth.svg" alt="Auth Logo" width="60" height="60" />
  </a>
</p>

<h1 align="center">asok-auth-providers</h1>

<p align="center">
  <a href="https://pypi.org/project/asok-auth-providers/">
    <img src="https://img.shields.io/pypi/v/asok-auth-providers.svg" alt="PyPI version" />
  </a>
</p>

<p align="center">
  <strong>OAuth2 Providers</strong> pack for the <strong>Asok Framework</strong>.
</p>

<p align="center">
  Ships ready-to-use Google, GitHub, Microsoft, Apple, Discord, Facebook, GitLab, LinkedIn, and Twitch sign-in flows, templates, and style sheets.
</p>

## Resources

* **PyPI Project**: [pypi.org/project/asok-auth-providers](https://pypi.org/project/asok-auth-providers/)
* **Asok Framework**: [asok-framework.com](https://asok-framework.com/)
* **Asok Repository**: [github.com/asok-framework/asok](https://github.com/asok-framework/asok)
* **Extension Repository**: [github.com/codewithmpia/asok-auth-providers](https://github.com/codewithmpia/asok-auth-providers)


## Installation

```bash
pip install asok-auth-providers
```

## Quick start

```python
# wsgi.py
from asok import Asok
from asok_auth_providers import AsokAuthProvidersExtension

app = Asok()

app.config["OAUTH_PROVIDERS"] = {
    "google": {
        "client_id": "...", 
        "client_secret": "...", 
        "label": "Google Workspace"
    },
    ...
}

def on_oauth_login(request, user_info):
    """Find or create a local user, then call request.login(user)."""
    from src.models.user import User
    user = User.find(email=user_info["email"]) or User.query().create(
        email=user_info["email"],
        name=user_info["name"],
    )
    request.login(user)

app.register_extension(AsokAuthProvidersExtension(
    app,
    on_login=on_oauth_login,
    login_redirect="/dashboard",
    login_failed_redirect="/login",
    compact=True,
    label_format="Connecter avec {}",
))
```

## Extension Anatomy

When you register `AsokAuthProvidersExtension` with your `Asok` app, it registers and manages the following components:

### 1. Routes & Page Handlers
The extension dynamically registers the following directory-based routes using the dynamic parameter `[provider]` folder:
* **`GET /auth/<provider>/login`**: Redirects the user to the provider's authorization consent screen.
* **`GET /auth/<provider>/callback`**: Receives the callback, validates security state keys, performs backend token exchanges, retrieves user profiles, executes your custom `on_login` callback, and redirects the user.

### 2. Template Helpers & Globals
The extension exposes the following context helper variables and callable functions to all templates:
* **`oauth_providers`**: The dictionary of brand names and default capitalized labels.
* **`oauth_icon(provider)`**: Outputs the inline SVG logo element for the selected provider.
* **`oauth_login_url(provider, next_url)`**: Generates the routing login URLs (e.g., `/auth/google/login?next=/dashboard`).
* **`oauth_providers_css()`**: Emits the standard `<link>` stylesheet element for the buttons.
* **`oauth_compact` & `oauth_label_format`**: The default layout preferences configured on your Python extension registry.

### 3. Static Assets
* **`/css/oauth-buttons.css`**: The stylesheet specifying sizes, hover scaling transitions, active states, flex grids, and brand background colors.


## Sign-in buttons

The template renders the button elements directly without a wrapper `div`. This allows complete freedom to wrap and style the layout however you want (for example, wrapping them in a flex container using Tailwind CSS or custom styles):

```html
<div class="flex flex-wrap gap-2">
    {% include "auth_providers/buttons.html" %}
</div>
```

To customize the provider list, set `providers` before the include:

```html
{% set providers = ["google", "github"] %}
{% include "auth_providers/buttons.html" %}
```

To customize the button labels, set a `labels` dictionary before the include (which maps provider names to custom strings), or provide a `label_format` template string (where `{}` is replaced by the provider's label):

```html
{% set labels = {"google": "Google Workspace"} %}
{% set label_format = "Connecter avec {}" %}
{% include "auth_providers/buttons.html" %}
```

To render compact buttons (only showing the brand icons without text):

```html
{% set compact = true %}
{% include "auth_providers/buttons.html" %}
```

To pass custom CSS classes directly to the elements (perfect for Tailwind CSS layouts):

```html
{# Completely override the default button classes #}
{% set button_class = "flex items-center rounded-lg px-4 py-2 text-white font-medium" %}

{# Or append extra classes to the default layout styles #}
{% set extra_class = "shadow hover:shadow-md transition-shadow" %}

{# Append classes to the inner label text span (e.g. for responsive hiding) #}
{% set label_class = "hidden md:inline-block ml-2" %}

{% include "auth_providers/buttons.html" %}
```

To preserve a post-login redirect:

```html
{% set next_url = "/dashboard" %}
{% include "auth_providers/buttons.html" %}
```

Include the default CSS:

```html
<link rel="stylesheet" href="/css/oauth-buttons.min.css">
```

## Configuration

Set `app.config["OAUTH_PROVIDERS"]` to a dict mapping provider names to `{client_id, client_secret}` credentials.

To avoid hardcoding sensitive credentials in your codebase, it is highly recommended to load them from environment variables (defined in your `.env` file).

### Example `.env` file

```env
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
```

### Loading in `wsgi.py`

```python
import os

app.config["OAUTH_PROVIDERS"] = {
    "google": {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "label": "Google Workspace"
    },
    "github": {
        "client_id": os.environ.get("GITHUB_CLIENT_ID"),
        "client_secret": os.environ.get("GITHUB_CLIENT_SECRET"),
    },
}
```

Only providers explicitly present in the dict are enabled — the extension will never auto-enable a provider without credentials.

> [!IMPORTANT]
> **Understanding `client_id` and `client_secret`**
>
> These are **not** your personal user credentials (like your email address, username, login password, or SMTP app-specific passwords).
>
> Instead, they are the **OAuth2 Application Credentials** generated by registering a web application on each provider's developer portal:
> * **Google**: Register on the [Google Cloud Console](https://console.cloud.google.com/) (APIs & Services > Credentials)
> * **GitHub**: Register a new OAuth App on [GitHub Developer Settings](https://github.com/settings/developers)
> * **Microsoft**: Register under App Registrations in the [Microsoft Entra ID Portal](https://entra.microsoft.com/)
> * **Apple**: Configure a Service ID on the [Apple Developer Account](https://developer.apple.com/account/) (Certificates, Identifiers & Profiles)
> * **Discord**: Create an application on the [Discord Developer Portal](https://discord.com/developers/applications)
> * **Facebook**: Register an App on the [Meta for Developers](https://developers.facebook.com/) portal
> * **GitLab**: Add an application in [GitLab User Applications Settings](https://gitlab.com/-/profile/applications)
> * **LinkedIn**: Register on the [LinkedIn Developer Portal](https://developer.linkedin.com/)
> * **Twitch**: Register your application in the [Twitch Developer Console](https://dev.twitch.tv/console)
>
> During registration on those developer portals, you must configure the **Redirect URI / Callback URL** to point to your application callback URL:
> `https://<your-domain>/auth/<provider>/callback` (or `http://127.0.0.1:8000/auth/github/callback` during local development).


### Customizing Labels and Layout Defaults

You can configure default layout parameters directly when initializing `AsokAuthProvidersExtension` in your Python code:

* `compact` (bool): If `True`, renders only the brand logo icons without text by default. (Default: `False`)
* `label_format` (str): A format pattern string (e.g., `"Connecter avec {}"`) to format button text by default. (Default: `""`)

For example:

```python
app.register_extension(AsokAuthProvidersExtension(
    app,
    on_login=on_oauth_login,
    compact=True,
    label_format="Se connecter avec {}"
))
```

Additionally, you can specify custom labels for individual providers directly in `app.config["OAUTH_PROVIDERS"]` using the `label` key:

```python
app.config["OAUTH_PROVIDERS"] = {
    "google": {
        "client_id": "...",
        "client_secret": "...",
        "label": "Google Workspace"  # Will render as: "Se connecter avec Google Workspace"
    }
}
```

You can also set `APP_URL` to lock the callback host (recommended in
production to prevent host-header tampering):

```python
app.config["APP_URL"] = "https://app.example.com"
```

Otherwise the callback URL is reconstructed from the current request's
scheme and `Host` header.

## Supported providers

| Provider  | Notes                                                      |
| --------- | ---------------------------------------------------------- |
| google    | Already in `asok.auth.OAuth` core, re-exposed here.        |
| github    | Already in `asok.auth.OAuth` core, re-exposed here.        |
| microsoft | Common (multi-tenant) authority endpoint.                  |
| apple     | `id_token` JWT decode (no userinfo endpoint).              |
| discord   | Requires `identify email` scopes.                          |
| facebook  | Requires `email public_profile` scopes.                    |
| gitlab    | Hosted gitlab.com only; self-hosted needs a custom config. |
| linkedin  | OpenID Connect userinfo endpoint.                          |
| twitch    | Requires `user:read:email` scope.                          |

## Security notes

- The OAuth `state` parameter is generated with `secrets.token_urlsafe(32)`
  and stored in the session. It is **popped** during the callback, so a
  callback URL cannot be replayed.
- Apple's `id_token` is JWT-decoded for claim extraction; signature
  verification against Apple's JWKS should be layered on top in production.
- `APP_URL` is honored when present, so the callback URL is not subject to
  `Host` header tampering.

## Hooks

`AsokAuthProvidersExtension(on_login=...)` takes a callback `(request, user_info) -> None` that is executed when the OAuth provider returns user profile information successfully. 

### The `user_info` Structure

The `user_info` argument is a normalized dictionary:

```python
{
    "provider":    "google",
    "provider_id": "1234567890",
    "email":       "user@example.com",
    "name":        "User Name",
    "picture":     "https://...",          # URL to their profile avatar
    "raw":         {...},                  # The raw, unfiltered provider response
}
```

### Implementing `on_login`

In your login hook, you can query your database to find or create the user, update their profile metadata (such as their name or picture URL), and log them into the Asok session:

```python
def on_oauth_login(request, user_info):
    from src.models.user import User

    # Find an existing user by email
    user = User.find(email=user_info["email"])

    if not user:
        # Create a new user account if they don't exist
        user = User.create(
            email=user_info["email"],
            name=user_info["name"],
            picture=user_info["picture"],
            oauth_provider=user_info["provider"],
            oauth_id=user_info["provider_id"]
        )
    else:
        # Update existing user profile assets (e.g. name or avatar URL)
        user.update(
            name=user_info["name"] or user.name,
            picture=user_info["picture"] or user.picture,
            oauth_provider=user_info["provider"],
            oauth_id=user_info["provider_id"]
        )

    # Log the user into the Asok session
    request.login(user)
```

Once `request.login(user)` is called, the logged-in user becomes globally accessible in all your templates and controllers via the `request.user` property:

```html
<!-- Inside any page template -->
<div class="profile-card">
    {% if request.user.picture %}
        <img src="{{ request.user.picture }}" alt="{{ request.user.name }}">
    {% endif %}
    <h2>Welcome back, {{ request.user.name }}!</h2>
    <p>Logged in via {{ request.user.oauth_provider | capitalize }}</p>
</div>
```

If no `on_login` callback is provided, the normalized `user_info` dict is stashed in `request.session["oauth_user_info"]`, and the user is redirected to `login_redirect`.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
