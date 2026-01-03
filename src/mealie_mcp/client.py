"""Async HTTP client wrapper for Mealie API."""

import base64
import logging
import os
from datetime import datetime
from typing import Any

import httpx

from mealie_mcp.context import get_current_user
from mealie_mcp.models import (
    Category,
    ErrorResponse,
    MealPlanEntry,
    Recipe,
    RecipeCreate,
    RecipeSummary,
    ShoppingList,
    ShoppingListItem,
    ShoppingListSummary,
    Tag,
    TimelineEvent,
    TimelineEventCreate,
    TimelineEventType,
)
from mealie_mcp.user_tokens import get_token_store

logger = logging.getLogger(__name__)


class MealieClient:
    """Async client for interacting with the Mealie API."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        timeout: float = 30.0,
        user_id: str | None = None,
    ):
        """Initialize the Mealie client.

        Args:
            base_url: Mealie API base URL (e.g., http://mealie:9000/api)
            token: Mealie API bearer token
            timeout: Request timeout in seconds
            user_id: OAuth user ID (for logging/debugging)
        """
        self.base_url = base_url or os.getenv("MEALIE_URL", "http://localhost:9000/api")
        self.token = token or os.getenv("MEALIE_TOKEN", "")
        self.timeout = timeout
        self.user_id = user_id
        self._client: httpx.AsyncClient | None = None
        self._group_id: str | None = None  # Cache the user's group ID
        
        if user_id:
            logger.debug(f"Created Mealie client for user: {user_id}")

    @property
    def headers(self) -> dict[str, str]:
        """Get authorization headers."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=self.headers,
                timeout=self.timeout,
            )
        return self._client

    async def get_group_id(self) -> str | None:
        """Get the current user's group ID (cached after first call)."""
        if self._group_id is not None:
            return self._group_id

        result = await self._request("GET", "/users/self")
        if isinstance(result, dict) and "groupId" in result:
            self._group_id = result["groupId"]
            return self._group_id

        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[Any] | ErrorResponse:
        """Make an HTTP request to the Mealie API.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            params: Query parameters
            json: JSON body for POST/PUT requests

        Returns:
            Parsed JSON response or ErrorResponse on failure
        """
        client = await self._get_client()

        try:
            response = await client.request(
                method=method,
                url=endpoint,
                params=params,
                json=json,
            )

            if response.status_code == 401:
                return ErrorResponse.auth_error("Invalid or expired Mealie API token")

            if response.status_code == 404:
                return ErrorResponse.not_found("Resource", endpoint)

            response.raise_for_status()

            if response.status_code == 204:
                return {"success": True}

            return response.json()

        except httpx.ConnectError:
            return ErrorResponse.api_error(f"Cannot connect to Mealie at {self.base_url}")
        except httpx.TimeoutException:
            return ErrorResponse.api_error("Request to Mealie timed out")
        except httpx.HTTPStatusError as e:
            return ErrorResponse.api_error(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            return ErrorResponse.api_error(f"Unexpected error: {str(e)}")

    # Recipe Methods
    async def search_recipes(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[RecipeSummary] | ErrorResponse:
        """Search recipes with optional filters.

        Args:
            query: Text search term
            tags: Filter by tag slugs
            categories: Filter by category slugs
            page: Page number (1-indexed)
            per_page: Results per page

        Returns:
            List of recipe summaries or error
        """
        params: dict[str, Any] = {
            "page": page,
            "perPage": per_page,
        }

        if query:
            params["search"] = query
        if tags:
            params["tags"] = tags
        if categories:
            params["categories"] = categories

        result = await self._request("GET", "/recipes", params=params)

        if isinstance(result, ErrorResponse):
            return result

        # Handle paginated response
        if isinstance(result, dict) and "items" in result:
            return [RecipeSummary.model_validate(r) for r in result["items"]]

        return [RecipeSummary.model_validate(r) for r in result]

    async def get_recipe(self, slug: str) -> Recipe | ErrorResponse:
        """Get full recipe details by slug.

        Args:
            slug: Recipe slug or ID

        Returns:
            Complete recipe or error
        """
        result = await self._request("GET", f"/recipes/{slug}")

        if isinstance(result, ErrorResponse):
            if result.code == "NOT_FOUND":
                return ErrorResponse.not_found("Recipe", slug)
            return result

        return Recipe.model_validate(result)

    async def list_tags(self) -> list[Tag] | ErrorResponse:
        """Get all available tags.

        Returns:
            List of tags or error
        """
        result = await self._request("GET", "/organizers/tags")

        if isinstance(result, ErrorResponse):
            return result

        # Handle paginated response
        items = result.get("items", result) if isinstance(result, dict) else result
        return [Tag.model_validate(t) for t in items]

    async def list_categories(self) -> list[Category] | ErrorResponse:
        """Get all available categories.

        Returns:
            List of categories or error
        """
        result = await self._request("GET", "/organizers/categories")

        if isinstance(result, ErrorResponse):
            return result

        # Handle paginated response
        items = result.get("items", result) if isinstance(result, dict) else result
        return [Category.model_validate(c) for c in items]

    # Meal Plan Methods
    async def get_meal_plan(
        self, start_date: str, end_date: str
    ) -> list[MealPlanEntry] | ErrorResponse:
        """Get meal plans for a date range.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of meal plan entries or error
        """
        params = {
            "start_date": start_date,
            "end_date": end_date,
        }

        result = await self._request("GET", "/households/mealplans", params=params)

        if isinstance(result, ErrorResponse):
            return result

        # Handle paginated response
        items = result.get("items", result) if isinstance(result, dict) else result
        return [MealPlanEntry.model_validate(e) for e in items]

    async def create_meal_plan_entry(
        self, date: str, recipe_id: str, entry_type: str = "dinner"
    ) -> MealPlanEntry | ErrorResponse:
        """Create a meal plan entry.

        Args:
            date: Date for the meal (YYYY-MM-DD)
            recipe_id: Recipe slug or UUID
            entry_type: Meal type (breakfast, lunch, dinner, side, snack)

        Returns:
            Created meal plan entry or error
        """
        # If recipe_id looks like a slug (not a UUID), look up the UUID
        if not self._is_uuid(recipe_id):
            recipe = await self.get_recipe(recipe_id)
            if isinstance(recipe, ErrorResponse):
                return recipe
            recipe_id = recipe.id

        body = {
            "date": date,
            "entryType": entry_type,
            "recipeId": recipe_id,
        }

        result = await self._request("POST", "/households/mealplans", json=body)

        if isinstance(result, ErrorResponse):
            return result

        return MealPlanEntry.model_validate(result)
    
    def _is_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID."""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))

    async def delete_meal_plan_entry(self, entry_id: str) -> dict[str, Any] | ErrorResponse:
        """Delete a meal plan entry.

        Args:
            entry_id: Meal plan entry ID

        Returns:
            Success status or error
        """
        result = await self._request("DELETE", f"/households/mealplans/{entry_id}")

        if isinstance(result, ErrorResponse):
            if result.code == "NOT_FOUND":
                return ErrorResponse.not_found("Meal plan entry", entry_id)
            return result

        return {"success": True, "message": f"Deleted meal plan entry {entry_id}"}

    # Shopping List Methods
    async def get_shopping_lists(self) -> list[ShoppingListSummary] | ErrorResponse:
        """Get all shopping lists.

        Returns:
            List of shopping list summaries or error
        """
        result = await self._request("GET", "/households/shopping/lists")

        if isinstance(result, ErrorResponse):
            return result

        # Handle paginated response
        items = result.get("items", result) if isinstance(result, dict) else result
        return [ShoppingListSummary.model_validate(s) for s in items]

    async def get_shopping_list(self, list_id: str) -> ShoppingList | ErrorResponse:
        """Get a specific shopping list with items.

        Args:
            list_id: Shopping list ID

        Returns:
            Shopping list with items or error
        """
        result = await self._request("GET", f"/households/shopping/lists/{list_id}")

        if isinstance(result, ErrorResponse):
            if result.code == "NOT_FOUND":
                return ErrorResponse.not_found("Shopping list", list_id)
            return result

        return ShoppingList.model_validate(result)

    async def add_shopping_list_item(
        self, list_id: str, note: str, quantity: float = 1
    ) -> ShoppingListItem | ErrorResponse:
        """Add an item to a shopping list.

        Args:
            list_id: Shopping list ID
            note: Item description
            quantity: Item quantity

        Returns:
            Created item or error
        """
        body = {
            "note": note,
            "quantity": quantity,
            "checked": False,
        }

        result = await self._request(
            "POST", f"/households/shopping/lists/{list_id}/items", json=body
        )

        if isinstance(result, ErrorResponse):
            return result

        return ShoppingListItem.model_validate(result)

    async def delete_shopping_list_item(
        self, list_id: str, item_id: str
    ) -> dict[str, Any] | ErrorResponse:
        """Remove an item from a shopping list.

        Args:
            list_id: Shopping list ID
            item_id: Item ID to remove

        Returns:
            Success status or error
        """
        result = await self._request(
            "DELETE", f"/households/shopping/lists/{list_id}/items/{item_id}"
        )

        if isinstance(result, ErrorResponse):
            return result

        return {"success": True}

    async def clear_checked_items(self, list_id: str) -> dict[str, Any] | ErrorResponse:
        """Remove all checked items from a shopping list.

        Args:
            list_id: Shopping list ID

        Returns:
            Success status with count of removed items or error
        """
        # First get the list to find checked items
        shopping_list = await self.get_shopping_list(list_id)

        if isinstance(shopping_list, ErrorResponse):
            return shopping_list

        checked_items = [item for item in shopping_list.list_items if item.checked]

        if not checked_items:
            return {"success": True, "removed_count": 0, "message": "No checked items to remove"}

        # Delete each checked item
        removed_count = 0
        for item in checked_items:
            result = await self.delete_shopping_list_item(list_id, item.id)
            if not isinstance(result, ErrorResponse):
                removed_count += 1

        return {
            "success": True,
            "removed_count": removed_count,
            "message": f"Removed {removed_count} checked items",
        }

    # Recipe Write Methods
    async def create_recipe(self, name: str) -> str | ErrorResponse:
        """Create a new recipe with just a name.

        Args:
            name: Recipe name

        Returns:
            Recipe slug or error
        """
        result = await self._request("POST", "/recipes", json={"name": name})

        if isinstance(result, ErrorResponse):
            return result

        # API returns the slug as a string
        if isinstance(result, str):
            return result

        return ErrorResponse.api_error("Unexpected response format from create recipe")

    async def update_recipe(self, slug: str, data: dict[str, Any]) -> Recipe | ErrorResponse:
        """Update an existing recipe.

        Args:
            slug: Recipe slug
            data: Recipe data to update

        Returns:
            Updated recipe or error
        """
        result = await self._request("PATCH", f"/recipes/{slug}", json=data)

        if isinstance(result, ErrorResponse):
            return result

        return Recipe.model_validate(result)

    async def delete_recipe(self, slug: str) -> dict[str, Any] | ErrorResponse:
        """Delete a recipe.

        Args:
            slug: Recipe slug

        Returns:
            Success status or error
        """
        result = await self._request("DELETE", f"/recipes/{slug}")

        if isinstance(result, ErrorResponse):
            return result

        return {"success": True, "message": f"Recipe '{slug}' deleted"}

    async def import_recipe_from_url(
        self, url: str, include_tags: bool = False
    ) -> str | ErrorResponse:
        """Import a recipe from a URL.

        Args:
            url: Recipe URL to scrape
            include_tags: Whether to include tags from the source

        Returns:
            Recipe slug or error
        """
        result = await self._request(
            "POST",
            "/recipes/create/url",
            json={"url": url, "includeTags": include_tags},
        )

        if isinstance(result, ErrorResponse):
            return result

        # API returns the slug as a string
        if isinstance(result, str):
            return result

        return ErrorResponse.api_error("Unexpected response format from URL import")

    async def update_recipe_last_made(
        self, slug: str, timestamp: datetime | None = None
    ) -> dict[str, Any] | ErrorResponse:
        """Update a recipe's last made timestamp.

        Args:
            slug: Recipe slug
            timestamp: When the recipe was made (defaults to now)

        Returns:
            Success status or error
        """
        if timestamp is None:
            timestamp = datetime.now()

        result = await self._request(
            "PATCH",
            f"/recipes/{slug}/last-made",
            json={"timestamp": timestamp.isoformat()},
        )

        if isinstance(result, ErrorResponse):
            return result

        return {"success": True, "message": f"Marked '{slug}' as made at {timestamp.isoformat()}"}

    # Timeline Methods
    async def create_timeline_event(
        self,
        recipe_id: str,
        subject: str,
        event_type: TimelineEventType = TimelineEventType.COMMENT,
        event_message: str | None = None,
        timestamp: datetime | None = None,
    ) -> TimelineEvent | ErrorResponse:
        """Create a timeline event for a recipe.

        Args:
            recipe_id: Recipe ID (UUID)
            subject: Event subject/title
            event_type: Type of event (system, info, comment)
            event_message: Optional event details
            timestamp: Event timestamp (defaults to now)

        Returns:
            Created timeline event or error
        """
        body: dict[str, Any] = {
            "recipeId": recipe_id,
            "subject": subject,
            "eventType": event_type.value,
        }

        if event_message:
            body["eventMessage"] = event_message

        if timestamp:
            body["timestamp"] = timestamp.isoformat()

        result = await self._request("POST", "/recipes/timeline/events", json=body)

        if isinstance(result, ErrorResponse):
            return result

        return TimelineEvent.model_validate(result)

    async def get_recipe_timeline(
        self, recipe_id: str, page: int = 1, per_page: int = 20
    ) -> list[TimelineEvent] | ErrorResponse:
        """Get timeline events for a recipe.

        Args:
            recipe_id: Recipe ID (UUID)
            page: Page number
            per_page: Results per page

        Returns:
            List of timeline events or error
        """
        params = {
            "page": page,
            "perPage": per_page,
            "queryFilter": f'recipeId = "{recipe_id}"',
        }

        result = await self._request("GET", "/recipes/timeline/events", params=params)

        if isinstance(result, ErrorResponse):
            return result

        # Handle paginated response
        items = result.get("items", result) if isinstance(result, dict) else result
        return [TimelineEvent.model_validate(e) for e in items]

    async def upload_recipe_image(
        self, slug: str, image_data: bytes, extension: str = "jpg"
    ) -> dict[str, Any] | ErrorResponse:
        """Upload an image for a recipe.

        Args:
            slug: Recipe slug
            image_data: Raw image bytes
            extension: Image file extension (jpg, png, webp)

        Returns:
            Upload result or error
        """
        client = await self._get_client()

        try:
            # Use multipart form data for image upload
            files = {"image": (f"image.{extension}", image_data, f"image/{extension}")}
            data = {"extension": extension}

            response = await client.put(
                f"/recipes/{slug}/image",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self.token}"},
            )

            if response.status_code == 401:
                return ErrorResponse.auth_error("Invalid or expired Mealie API token")

            if response.status_code == 404:
                return ErrorResponse.not_found("Recipe", slug)

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            return ErrorResponse.api_error(f"HTTP {e.response.status_code}: {e.response.text}")
        except Exception as e:
            return ErrorResponse.api_error(f"Image upload failed: {str(e)}")

    async def upload_recipe_image_from_base64(
        self, slug: str, base64_data: str, extension: str = "jpg"
    ) -> dict[str, Any] | ErrorResponse:
        """Upload an image for a recipe from base64 data.

        Args:
            slug: Recipe slug
            base64_data: Base64-encoded image data (with or without data URI prefix)
            extension: Image file extension (jpg, png, webp)

        Returns:
            Upload result or error
        """
        # Strip data URI prefix if present
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]

        try:
            image_bytes = base64.b64decode(base64_data)
        except Exception as e:
            return ErrorResponse.validation_error(f"Invalid base64 data: {str(e)}")

        return await self.upload_recipe_image(slug, image_bytes, extension)


# Singleton client instance (single-tenant per server process)
_client_instance: MealieClient | None = None


def get_client() -> MealieClient:
    """Get or create the singleton Mealie client for this server instance.
    
    Each server process serves one user, with their MEALIE_TOKEN from the environment.
    
    Returns:
        MealieClient configured with MEALIE_TOKEN from environment
    """
    global _client_instance
    
    if _client_instance is None:
        # Get configuration from environment
        base_url = os.getenv("MEALIE_URL")
        token = os.getenv("MEALIE_TOKEN")
        user_id = os.getenv("MCP_USER", "unknown")
        
        if not token:
            raise ValueError(
                "MEALIE_TOKEN environment variable is required. "
                "Set it in .env file or systemd service."
            )
        
        _client_instance = MealieClient(
            base_url=base_url,
            token=token,
            user_id=user_id,
        )
        
        logger.info(f"Created Mealie client for user: {user_id}")
    
    return _client_instance
    
    return client
