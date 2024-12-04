from typing import Any, Callable, Collection, Mapping, Sequence

import pandas as pd
from airflow.exceptions import AirflowException
from airflow.models import BaseOperator
from airflow.utils.context import Context
from airflow.utils.decorators import apply_defaults
from airflow.utils.operator_helpers import KeywordParameters
from airflow.utils.context import context_merge

from airflow_provider_tm1.hooks.tm1 import TM1Hook


class TM1MDXQueryOperator(BaseOperator):
    """
    This operator executes an MDX query

    :param mdx: Valid MDX Query
    :param top: Int, number of cells to return (counting from top)
    :param skip: Int, number of cells to skip (counting from top)
    :param skip_zeros: skip zeros in cellset (irrespective of zero suppression in MDX / view)
    :param skip_consolidated_cells: skip consolidated cells in cellset
    :param skip_rule_derived_cells: skip rule derived cells in cellset
    :param sandbox_name: str
    :param include_attributes: include attribute columns
    :param use_iterative_json: use iterative json parsing to reduce memory consumption significantly.
    Comes at a cost of 3-5% performance.
    :param use_compact_json: bool
    :param use_blob: Has better performance on datasets > 1M cells and lower memory footprint in any case.
    :param shaped: preserve shape of view/mdx in data frame
    :param mdx_headers: boolean, fully qualified hierarchy name as header instead of simple dimension name
    :param fillna_numeric_attributes: boolean, fills empty numerical attributes with fillna_numeric_attributes_value
    :param fillna_string_attributes: boolean, fills empty string attributes with fillna_string_attributes_value
    :param fillna_numeric_attributes_value: Any, value with which to replace na if fillna_numeric_attributes is True
    :param fillna_string_attributes_value: Any, value with which to replace na if fillna_string_attributes is True
    :param tm1_conn_id: The Airflow connection used for TM1 credentials.
    :param tm1_dry_run: in Dry mode the Operator will skip the execution. Default value is False.
    :param post_callable: A reference to a callable, which is executed taking after the MDX completed using its result DataFrame as input.
    :param op_kwargs: a dictionary of keyword arguments that will get unpacked
        in your function
    :param op_args: a list of positional arguments that will get unpacked when
        calling your callable
    :param templates_dict: a dictionary where the values are templates that
        will get templated by the Airflow engine sometime between
        ``__init__`` and ``execute`` takes place and are made available
        in your callable's context after the template has been applied. (templated)
    :param templates_exts: a list of file extensions to resolve while
        processing templated fields, for examples ``['.sql', '.hql']``
    :param show_return_value_in_logs: a bool value whether to show return_value
        logs. Defaults to True, which allows return value log output.
        It can be set to False to prevent log output of return value when you return huge data
        such as transmission a large amount of XCom to TaskAPI.
    """

    template_fields: Sequence[str] = ("templates_dict", "op_args", "op_kwargs", "mdx")
    template_fields_renderers = {"templates_dict": "json", "op_args": "py", "op_kwargs": "py", "mdx": "mdx"}
    BLUE = "#ffefeb"
    ui_color = BLUE

    # since we won't mutate the arguments, we should just do the shallow copy
    # there are some cases we can't deepcopy the objects(e.g protobuf).
    shallow_copy_attrs: Sequence[str] = (
        "post_callable",
        "op_kwargs",
    )

    @apply_defaults
    def __init__(
            self,
            *,
            mdx: str,
            top: int = None,
            skip: int = None,
            skip_zeros: bool = True,
            skip_consolidated_cells: bool = False,
            skip_rule_derived_cells: bool = False,
            sandbox_name: str = None,
            include_attributes: bool = False,
            use_iterative_json: bool = False,
            use_compact_json: bool = False,
            use_blob: bool = False,
            shaped: bool = False,
            mdx_headers: bool = False,
            fillna_numeric_attributes: bool = False,
            fillna_numeric_attributes_value: Any = 0,
            fillna_string_attributes: bool = False,
            fillna_string_attributes_value: Any = '',
            tm1_conn_id: str = "tm1_default",
            tm1_dry_run: bool = False,
            tm1_params: dict = {},
            post_callable: Callable = None,
            op_args: Collection[Any] | None = None,
            op_kwargs: Mapping[str, Any] | None = None,
            templates_dict: dict[str, Any] | None = None,
            templates_exts: Sequence[str] | None = None,
            show_return_value_in_logs: bool = True,
            **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.mdx = mdx
        if not callable(post_callable):
            raise AirflowException("`post_callable` param must be callable")
        self.top = top
        self.skip = skip
        self.skip_zeros = skip_zeros
        self.skip_consolidated_cells = skip_consolidated_cells
        self.skip_rule_derived_cells = skip_rule_derived_cells
        self.sandbox_name = sandbox_name
        self.include_attributes = include_attributes
        self.use_iterative_json = use_iterative_json
        self.use_compact_json = use_compact_json
        self.use_blob = use_blob
        self.shaped = shaped
        self.mdx_headers = mdx_headers
        self.fillna_numeric_attributes = fillna_numeric_attributes
        self.fillna_numeric_attributes_value = fillna_numeric_attributes_value
        self.fillna_string_attributes = fillna_string_attributes
        self.fillna_string_attributes_value = fillna_string_attributes_value
        self.tm1_conn_id = tm1_conn_id
        self.tm1_dry_run = tm1_dry_run
        self.tm1_params = tm1_params
        self.post_callable = post_callable
        self.op_args = op_args or ()
        self.op_kwargs = op_kwargs or {}
        self.templates_dict = templates_dict
        if templates_exts:
            self.template_ext = templates_exts
        self.show_return_value_in_logs = show_return_value_in_logs

    def execute(self, context: Context) -> None:

        if not self.tm1_dry_run:

            with TM1Hook(tm1_conn_id=self.tm1_conn_id).get_conn() as tm1:
                df = tm1.cells.execute_mdx_dataframe(mdx=self.mdx, top=self.top, skip=self.skip,
                                                     skip_zeros=self.skip_zeros,
                                                     skip_consolidated_cells=self.skip_consolidated_cells,
                                                     skip_rule_derived_cells=self.skip_rule_derived_cells,
                                                     sandbox_name=self.sandbox_name,
                                                     include_attributes=self.include_attributes,
                                                     use_iterative_json=self.use_iterative_json,
                                                     use_compact_json=self.use_compact_json,
                                                     use_blob=self.use_blob, shaped=self.shaped,
                                                     mdx_headers=self.mdx_headers,
                                                     fillna_numeric_attributes=self.fillna_numeric_attributes,
                                                     fillna_numeric_attributes_value=self.fillna_numeric_attributes_value,
                                                     fillna_string_attributes=self.fillna_string_attributes,
                                                     fillna_string_attributes_value=self.fillna_string_attributes_value,
                                                     **self.tm1_params,
                                                     )

                context_merge(context, self.op_kwargs, templates_dict=self.templates_dict)
                self.op_kwargs = self.determine_kwargs(context)

                return_value = self.execute_callable(df)
                if self.show_return_value_in_logs:
                    self.log.info("Done. Returned value was: %s", return_value)
                else:
                    self.log.info("Done. Returned value not shown")
                return return_value
        else:
            print("Execution TM1 MDX " + self.mdx + " in dry-run mode")

    def determine_kwargs(self, context: Mapping[str, Any]) -> Mapping[str, Any]:
        return KeywordParameters.determine(self.post_callable, self.op_args, context).unpacking()

    def execute_callable(self, df: pd.DataFrame) -> Any:
        """
        Call the python callable with the given arguments.

        :return: the return value of the call.
        """
        return self.post_callable(df, *self.op_args, **self.op_kwargs)