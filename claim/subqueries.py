from claim.models import Claim, ClaimDetail
from django.db.models import OuterRef, Subquery, Avg, Q, Sum, F, ExpressionWrapper, DecimalField, Subquery, OuterRef, Case, Value, When
from django.db.models.functions import Coalesce

# row_id = models.BinaryField(db_column='RowID', blank=True, null=True)

# subqueries
# Subquery for total_itm_adjusted
total_itm_adjusted_subquery = Claim.objects.filter(id=OuterRef('id')).annotate(
    total_itm_adjusted=Sum(
        F("items__qty_provided") * Coalesce("items__price_adjusted", "items__price_asked")
    )
).values('total_itm_adjusted')[:1]
# Subquery for total_srv_adjusted
total_srv_adjusted_subquery = Claim.objects.filter(id=OuterRef('id')).annotate(
    total_srv_adjusted=Sum(
        F("services__qty_provided") * Coalesce("services__price_adjusted", "services__price_asked")
    )
).values('total_srv_adjusted')[:1]
# Subquery for total_itm_approved
total_itm_approved_subquery = Claim.objects.filter(id=OuterRef('id')).annotate(
    total_itm_approved=Sum(
        Case(
            When(Q(status=Claim.STATUS_REJECTED, items__status=ClaimDetail.STATUS_REJECTED), then=Value(0)),
            default=Coalesce("items__qty_approved", "items__qty_provided", 0) * 
                Coalesce("items__price_approved", "services__price_adjusted", "items__price_asked"),
            output_field=DecimalField()
        )
    )
).values('total_itm_approved')[:1]
# Subquery for total_srv_approved
total_srv_approved_subquery = Claim.objects.filter(id=OuterRef('id')).annotate(
    total_srv_approved=Sum(
        Case(
            When(Q(status=Claim.STATUS_REJECTED, items__status=ClaimDetail.STATUS_REJECTED), then=Value(0)),
            default=Coalesce("services__qty_approved", "services__qty_provided", 0) *
            Coalesce("services__price_approved", "services__price_adjusted", "services__price_asked"),
            output_field=DecimalField()
        )
    )
).values('total_srv_approved')[:1]