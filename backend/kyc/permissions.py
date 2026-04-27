from rest_framework.permissions import BasePermission


class IsMerchant(BasePermission):
    message = "Only merchants can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_merchant())


class IsReviewer(BasePermission):
    message = "Only reviewers can perform this action."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_reviewer())


class IsOwnerMerchantOrReviewer(BasePermission):
    """
    Object-level: reviewers see everything; merchants only see their own submission.
    This is the key isolation check — stops merchant A from reading merchant B's data.
    """
    message = "You do not have permission to access this submission."

    def has_object_permission(self, request, view, obj):
        if request.user.is_reviewer():
            return True
        # Merchant can only access their own submission
        return obj.merchant_id == request.user.id
