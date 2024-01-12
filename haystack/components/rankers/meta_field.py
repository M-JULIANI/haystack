import logging
from collections import defaultdict
from typing import List, Dict, Any, Optional, Literal, Set
from dateutil.parser import parse
import yaml

from haystack import Document, component, default_to_dict

logger = logging.getLogger(__name__)


@component
class MetaFieldRanker:
    """
    Ranks Documents based on the value of their specific meta field.
    The ranking can be performed in descending order or ascending order.

    Usage example:
    ```
    from haystack import Document
    from haystack.components.rankers import MetaFieldRanker

    ranker = MetaFieldRanker(meta_field="rating")
    docs = [
        Document(text="Paris", meta={"rating": 1.3}),
        Document(text="Berlin", meta={"rating": 0.7}),
        Document(text="Barcelona", meta={"rating": 2.1}),
    ]

    output = ranker.run(documents=docs)
    docs = output["documents"]
    assert docs[0].text == "Barcelona"
    """

    def __init__(
        self,
        meta_field: str,
        weight: float = 1.0,
        top_k: Optional[int] = None,
        ranking_mode: Literal["reciprocal_rank_fusion", "linear_score"] = "reciprocal_rank_fusion",
        sort_order: Literal["ascending", "descending"] = "descending",
        infer_type: bool = True,
    ):
        """
        Creates an instance of MetaFieldRanker.

        :param meta_field: The name of the meta field to rank by.
        :param weight: In range [0,1].
                0 disables ranking by a meta field.
                0.5 content and meta fields have the same impact for the ranking.
                1 means ranking by a meta field only. The highest value comes first.
        :param top_k: The maximum number of Documents you want the Ranker to return per query. If not provided, the
                Ranker returns all documents it receives in the new ranking order.
        :param ranking_mode: The mode used to combine the Retriever's and Ranker's scores.
                Possible values are 'reciprocal_rank_fusion' (default) and 'linear_score'.
                Use the 'score' mode only with Retrievers or Rankers that return a score in range [0,1].
        :param sort_order: Whether to sort the meta field by ascending or descending order.
                Possible values are `descending` (default) and `ascending`.
        :param infer_type: Whether to try and infer the data type of meta value that is a string. For example, we have
                the field `"date": "2015-02-01"` we would infer the type of "date" to be a datetime object.
        """

        self.meta_field = meta_field
        self.weight = weight
        self.top_k = top_k
        self.ranking_mode = ranking_mode
        self.sort_order = sort_order
        self.infer_type = infer_type
        self._validate_params(
            weight=self.weight, top_k=self.top_k, ranking_mode=self.ranking_mode, sort_order=self.sort_order
        )

    def _validate_params(
        self,
        weight: float,
        top_k: Optional[int],
        ranking_mode: Literal["reciprocal_rank_fusion", "linear_score"],
        sort_order: Literal["ascending", "descending"],
    ):
        if top_k is not None and top_k <= 0:
            raise ValueError("top_k must be > 0, but got %s" % top_k)

        if weight < 0 or weight > 1:
            raise ValueError(
                "Parameter <weight> must be in range [0,1] but is currently set to '%s'.\n'0' disables sorting by a "
                "meta field, '0.5' assigns equal weight to the previous relevance scores and the meta field, and "
                "'1' ranks by the meta field only.\nChange the <weight> parameter to a value in range 0 to 1 when "
                "initializing the MetaFieldRanker." % self.weight
            )

        if ranking_mode not in ["reciprocal_rank_fusion", "linear_score"]:
            raise ValueError(
                "The value of parameter <ranking_mode> must be 'reciprocal_rank_fusion' or 'linear_score', but is "
                "currently set to '%s'.\nChange the <ranking_mode> value to 'reciprocal_rank_fusion' or "
                "'linear_score' when initializing the MetaFieldRanker." % ranking_mode
            )

        if sort_order not in ["ascending", "descending"]:
            raise ValueError(
                "The value of parameter <sort_order> must be 'ascending' or 'descending', but is currently set to '%s'.\n"
                "Change the <sort_order> value to 'ascending' or 'descending' when initializing the "
                "MetaFieldRanker." % sort_order
            )

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize object to a dictionary.
        """
        return default_to_dict(
            self,
            meta_field=self.meta_field,
            weight=self.weight,
            top_k=self.top_k,
            ranking_mode=self.ranking_mode,
            infer_type=self.infer_type,
        )

    @component.output_types(documents=List[Document])
    def run(
        self,
        documents: List[Document],
        top_k: Optional[int] = None,
        weight: Optional[float] = None,
        ranking_mode: Optional[Literal["reciprocal_rank_fusion", "linear_score"]] = None,
        sort_order: Optional[Literal["ascending", "descending"]] = None,
        infer_type: Optional[bool] = None,
    ):
        """
        Use this method to rank a list of Documents based on the selected meta field by:
        1. Sorting the Documents by the meta field in descending or ascending order.
        2. Merging the scores from the meta field with the scores from the previous component according to the strategy and weight provided.
        3. Returning the top-k documents.

        :param documents: Documents to be ranked.
        :param top_k: (optional) The number of Documents you want the Ranker to return.
                If not provided, the top_k provided at initialization time is used.
        :param weight: (optional) In range [0,1].
                0 disables ranking by a meta field.
                0.5 content and meta fields have the same impact for the ranking.
                1 means ranking by a meta field only. The highest value comes first.
                If not provided, the weight provided at initialization time is used.
        :param ranking_mode: (optional) The mode used to combine the Retriever's and Ranker's scores.
                Possible values are 'reciprocal_rank_fusion' (default) and 'linear_score'.
                Use the 'score' mode only with Retrievers or Rankers that return a score in range [0,1].
                If not provided, the ranking_mode provided at initialization time is used.
        :param sort_order: Whether to sort the meta field by ascending or descending order.
                Possible values are `descending` (default) and `ascending`.
                If not provided, the sort_order provided at initialization time is used.
        :param infer_type: Whether to try and infer the data type of meta value that is a string. For example, we have
                the field `"date": "2015-02-01"` we would infer the type of "date" to be a datetime object.
                If not provided, the infer_type provided at initialization time is used.
        """
        if not documents:
            return {"documents": []}

        top_k = top_k or self.top_k
        weight = weight or self.weight
        ranking_mode = ranking_mode or self.ranking_mode
        sort_order = sort_order or self.sort_order
        infer_type = infer_type or self.infer_type
        self._validate_params(weight=weight, top_k=top_k, ranking_mode=ranking_mode, sort_order=sort_order)

        # If the weight is 0 then ranking by meta field is disabled and the original documents should be returned
        if weight == 0:
            return {"documents": documents[:top_k]}

        docs_with_meta_field = []
        docs_missing_meta_field = []
        unique_meta_values = set()
        for document in documents:
            # Using try except block instead of .meta.get() to handle situation that the meta_value could be None
            try:
                meta_value = document.meta[self.meta_field]
                docs_with_meta_field.append(document)
                unique_meta_values.add(meta_value)
            except KeyError:
                docs_missing_meta_field.append(document)

        # If all docs are missing self.meta_field return original documents
        if len(docs_missing_meta_field) == len(documents):
            logger.warning(
                "The parameter <meta_field> is currently set to '%s', but none of the provided Documents with IDs %s have this meta key.\n"
                "Set <meta_field> to the name of a field that is present within the provided Documents.\n"
                "Returning the original Documents since there are no values to rank.",
                self.meta_field,
                ",".join([doc.id for doc in documents]),
            )
            return {"documents": documents[:top_k]}

        if len(docs_missing_meta_field) > 0:
            logger.warning(
                "The parameter <meta_field> is currently set to '%s' but the Documents with IDs %s don't have this meta key.\n"
                "These Documents will be placed at the end of the sorting order.",
                self.meta_field,
                ",".join([doc.id for doc in docs_missing_meta_field]),
            )

        # If all string type then try to infer using yaml.safe_load ??
        if infer_type and all(isinstance(d.meta[self.meta_field], str) for d in docs_with_meta_field):
            ...
        else:
            logger.warning(
                "The parameter <infer_type> is currently set to `%s`, but not all of meta values in the provided Documents are strings.\n"
                "Therefore,",
                infer_type,
            )

        # Sort the documents by self.meta_field
        reverse = sort_order == "descending"
        try:
            sorted_by_meta = sorted(docs_with_meta_field, key=lambda doc: doc.meta[self.meta_field], reverse=reverse)
        except TypeError as error:
            # Return original documents if mixed types that are not comparable are returned (e.g. int and list)
            logger.warning(
                "Tried to sort Documents with IDs %s, but got TypeError with the message: %s\n"
                "Returning the original Documents since meta field ranking is not possible.",
                ",".join([doc.id for doc in docs_missing_meta_field]),
                error,
            )
            return {"documents": documents[:top_k]}

        # Add the docs missing the meta_field back on the end
        sorted_documents = sorted_by_meta + docs_missing_meta_field
        # Merge the two ranked lists
        sorted_documents = self._merge_rankings(documents, sorted_documents)

        return {"documents": sorted_documents[:top_k]}

    def _check_all_same_type(self, documents: List[Document]) -> bool:
        all_types = {type(d.meta[self.meta_field]) for d in documents}
        return len(all_types) == 1

    def _merge_rankings(self, documents: List[Document], sorted_documents: List[Document]) -> List[Document]:
        """
        Merge the two different rankings for Documents sorted both by their content and by their meta field.
        """
        scores_map: Dict = defaultdict(int)

        if self.ranking_mode == "reciprocal_rank_fusion":
            for i, (document, sorted_doc) in enumerate(zip(documents, sorted_documents)):
                scores_map[document.id] += self._calculate_rrf(rank=i) * (1 - self.weight)
                scores_map[sorted_doc.id] += self._calculate_rrf(rank=i) * self.weight
        elif self.ranking_mode == "linear_score":
            for i, (document, sorted_doc) in enumerate(zip(documents, sorted_documents)):
                score = float(0)
                if document.score is None:
                    logger.warning("The score wasn't provided; defaulting to 0.")
                elif document.score < 0 or document.score > 1:
                    logger.warning(
                        "The score %s for Document %s is outside the [0,1] range; defaulting to 0",
                        document.score,
                        document.id,
                    )
                else:
                    score = document.score

                scores_map[document.id] += score * (1 - self.weight)
                scores_map[sorted_doc.id] += self._calc_linear_score(rank=i, amount=len(sorted_documents)) * self.weight

        for document in documents:
            document.score = scores_map[document.id]

        new_sorted_documents = sorted(documents, key=lambda doc: doc.score if doc.score else -1, reverse=True)
        return new_sorted_documents

    @staticmethod
    def _calculate_rrf(rank: int, k: int = 61) -> float:
        """
        Calculates the reciprocal rank fusion. The constant K is set to 61 (60 was suggested by the original paper,
        plus 1 as python lists are 0-based and the [paper](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) used 1-based ranking).
        """
        return 1 / (k + rank)

    @staticmethod
    def _calc_linear_score(rank: int, amount: int) -> float:
        """
        Calculate the meta field score as a linear score between the greatest and the lowest score in the list.
        This linear scaling is useful for:
          - Reducing the effect of outliers
          - Creating scores that are meaningfully distributed in the range [0,1],
             similar to scores coming from a Retriever or Ranker.
        """
        return (amount - rank) / amount
