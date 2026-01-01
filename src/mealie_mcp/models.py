"""Pydantic models for Mealie API responses and MCP tool parameters."""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# Enums
class MealType(str, Enum):
    """Types of meals for meal planning."""

    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SIDE = "side"
    SNACK = "snack"


# Base Models
class MealieBase(BaseModel):
    """Base model with common configuration."""

    model_config = ConfigDict(extra="ignore")


# Organizers (Tags & Categories)
class Tag(MealieBase):
    """Tag model."""

    id: str
    slug: str
    name: str


class Category(MealieBase):
    """Category model."""

    id: str
    slug: str
    name: str


# Recipe Models
class RecipeIngredient(MealieBase):
    """Recipe ingredient model."""

    quantity: float | None = None
    unit: str | None = None
    food: str | None = None
    note: str | None = None
    original_text: str | None = Field(None, alias="originalText")
    display: str | None = None


class RecipeInstruction(MealieBase):
    """Recipe instruction step."""

    id: str | None = None
    title: str | None = None
    text: str


class RecipeNutrition(MealieBase):
    """Recipe nutrition information."""

    calories: str | None = None
    fat_content: str | None = Field(None, alias="fatContent")
    protein_content: str | None = Field(None, alias="proteinContent")
    carbohydrate_content: str | None = Field(None, alias="carbohydrateContent")
    fiber_content: str | None = Field(None, alias="fiberContent")
    sodium_content: str | None = Field(None, alias="sodiumContent")
    sugar_content: str | None = Field(None, alias="sugarContent")


class RecipeSummary(MealieBase):
    """Summary of a recipe for list views."""

    id: str
    slug: str
    name: str
    description: str | None = None
    image: str | None = None
    tags: list[Tag] = Field(default_factory=list)
    recipe_category: list[Category] = Field(default_factory=list, alias="recipeCategory")
    total_time: str | None = Field(None, alias="totalTime")
    prep_time: str | None = Field(None, alias="prepTime")
    cook_time: str | None = Field(None, alias="cookTime")
    rating: int | None = None


class Recipe(RecipeSummary):
    """Full recipe details."""

    recipe_yield: str | None = Field(None, alias="recipeYield")
    recipe_ingredient: list[RecipeIngredient] = Field(
        default_factory=list, alias="recipeIngredient"
    )
    recipe_instructions: list[RecipeInstruction] = Field(
        default_factory=list, alias="recipeInstructions"
    )
    nutrition: RecipeNutrition | None = None
    notes: list[dict[str, Any]] = Field(default_factory=list)
    org_url: str | None = Field(None, alias="orgURL")


# Meal Plan Models
class MealPlanEntry(MealieBase):
    """A single meal plan entry."""

    id: str
    date: date
    entry_type: MealType = Field(alias="entryType")
    recipe_id: str | None = Field(None, alias="recipeId")
    recipe: RecipeSummary | None = None
    title: str | None = None
    text: str | None = None


class MealPlanCreate(BaseModel):
    """Model for creating a meal plan entry."""

    date: date
    entry_type: MealType = Field(alias="entryType")
    recipe_id: str = Field(alias="recipeId")


# Shopping List Models
class ShoppingListItem(MealieBase):
    """An item in a shopping list."""

    id: str
    shopping_list_id: str = Field(alias="shoppingListId")
    checked: bool = False
    quantity: float = 1
    unit: str | None = None
    food: str | None = None
    note: str | None = None
    display: str | None = None
    is_food: bool = Field(False, alias="isFood")


class ShoppingListSummary(MealieBase):
    """Summary of a shopping list."""

    id: str
    name: str


class ShoppingList(ShoppingListSummary):
    """Full shopping list with items."""

    list_items: list[ShoppingListItem] = Field(default_factory=list, alias="listItems")


class ShoppingListItemCreate(BaseModel):
    """Model for adding an item to a shopping list."""

    note: str
    quantity: float = 1
    checked: bool = False


# API Response Models
class PaginatedResponse(MealieBase):
    """Paginated API response wrapper."""

    page: int = 1
    per_page: int = Field(50, alias="perPage")
    total: int = 0
    total_pages: int = Field(0, alias="totalPages")
    items: list[Any] = Field(default_factory=list)


# Error Models
class ErrorResponse(BaseModel):
    """Structured error response for MCP tools."""

    error: bool = True
    code: str
    message: str

    @classmethod
    def not_found(cls, resource: str, identifier: str) -> "ErrorResponse":
        return cls(code="NOT_FOUND", message=f"{resource} '{identifier}' not found")

    @classmethod
    def auth_error(cls, message: str = "Authentication failed") -> "ErrorResponse":
        return cls(code="AUTH_ERROR", message=message)

    @classmethod
    def api_error(cls, message: str) -> "ErrorResponse":
        return cls(code="API_ERROR", message=message)

    @classmethod
    def validation_error(cls, message: str) -> "ErrorResponse":
        return cls(code="VALIDATION_ERROR", message=message)
