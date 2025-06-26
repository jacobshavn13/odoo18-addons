# -*- coding: utf-8 -*-
################################################################################
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Bhagyadev KP (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
################################################################################
import calendar
import io
import json
from datetime import datetime
import xlsxwriter
from odoo import api, fields, models
from odoo.tools.date_utils import get_month, get_fiscal_year, \
    get_quarter_number, subtract


class AccountTrialBalance(models.TransientModel):
    """For creating Trial Balance report"""
    _name = 'account.trial.balance'
    _description = 'Trial Balance Report'

    @api.model
    def view_report(self):
        """
        Generates a trial balance report for multiple accounts.
        Retrieves account information and calculates total debit and credit
        amounts for each account within the specified date range. Returns a list
        of dictionaries containing account details and transaction totals.

        :return: List of dictionaries representing the trial balance report.
        :rtype: list
        """
        account_ids = self.env['account.move.line'].search([]).mapped(
            'account_id')
        today = fields.Date.today()
        move_line_list = []
        for account_id in account_ids:
            initial_move_line_ids = self.env['account.move.line'].search(
                [('date', '<', get_month(today)[0]),
                 ('account_id', '=', account_id.id),
                 ('parent_state', '=', 'posted')])
            initial_total_debit = round(
                sum(initial_move_line_ids.mapped('debit')), 2)
            initial_total_credit = round(
                sum(initial_move_line_ids.mapped('credit')), 2)
            move_line_ids = self.env['account.move.line'].search(
                [('date', '>=', get_month(today)[0]),
                 ('account_id', '=', account_id.id),
                 ('date', '<=', get_month(today)[1]),
                 ('parent_state', '=', 'posted')])
            total_debit = round(sum(move_line_ids.mapped('debit')), 2)
            total_credit = round(sum(move_line_ids.mapped('credit')), 2)
            sum_debit = initial_total_debit + total_debit
            sum_credit = initial_total_credit + total_credit
            diff_credit_debit = sum_debit - sum_credit
            if diff_credit_debit > 0:
                end_total_debit = diff_credit_debit
                end_total_credit = 0.0
            else:
                end_total_debit = 0.0
                end_total_credit = abs(diff_credit_debit)
            data = {
                'account': account_id.display_name,
                'account_id': account_id.id,
                'journal_ids': self.env['account.journal'].search_read([], ['name']),
                'initial_total_debit': "{:,.2f}".format(initial_total_debit),
                'initial_total_credit': "{:,.2f}".format(initial_total_credit),
                'total_debit': total_debit,
                'total_credit': total_credit,
                'end_total_debit': "{:,.2f}".format(end_total_debit),
                'end_total_credit': "{:,.2f}".format(end_total_credit)
            }
            move_line_list.append(data)
        journal = {
            'journal_ids': self.env['account.journal'].search_read([], [
                'name'])
        }
        return move_line_list, journal

    @api.model
    def get_filter_values(self, start_date, end_date, comparison_number,
                          comparison_type, journal_list, analytic, options,
                          method):
        """
        Retrieves and calculates filtered values for generating a financial
        report.
        Retrieves and processes account movement data based on the provided
        filters. Calculates initial, dynamic, and end total debit and credit
        amounts for each account,considering date range, comparison type, and
        other filter criteria.

        :param str start_date: Start date of the reporting period.
        :param str end_date: End date of the reporting period.
        :param int comparison_number: Number of periods for comparison.
        :param str comparison_type: Type of comparison (month, year, quarter).
        :param list[int] journal_list: List of selected journal IDs.
        :param list[int] analytic: List of selected analytic line IDs.
        :param dict options: Additional filtering options (e.g., 'draft').
        :param dict method: Find the method.
        :return: List of dictionaries representing the financial report.
        :rtype: list
        """
        if options == {}:
            options = None
        if options is None:
            option_domain = ['posted']
        elif 'draft' in options:
            option_domain = ['posted', 'draft']
        if method == {}:
            method = None
        dynamic_total_debit = {}
        dynamic_date_num = {}
        dynamic_total_credit = {}
        account_ids = self.env['account.move.line'].search([]).mapped(
            'account_id')
        move_line_list = []
        start_date_first = \
            get_fiscal_year(datetime.strptime(start_date, "%Y-%m-%d").date())[
                0] if comparison_type == 'year' else datetime.strptime(
                start_date, "%Y-%m-%d").date()
        end_date_first = \
            get_fiscal_year(datetime.strptime(end_date, "%Y-%m-%d").date())[
                1] if comparison_type == 'year' else datetime.strptime(end_date,
                                                                       "%Y-%m-%d").date()
        for account_id in account_ids:
            start_date = start_date_first
            end_date = end_date_first
            if comparison_number:
                if comparison_type == 'month':
                    initial_start_date = subtract(start_date, months=eval(
                        comparison_number))
                elif comparison_type == 'year':
                    initial_start_date = subtract(start_date, years=eval(
                        comparison_number))
                else:
                    initial_start_date = subtract(start_date, months=eval(
                        comparison_number) * 3)
            else:
                initial_start_date = start_date
            domain = [('date', '<', initial_start_date),
                      ('account_id', '=', account_id.id),
                      ('parent_state', 'in', option_domain), ]
            if journal_list:
                domain.append(
                    ('journal_id', 'in', journal_list), )
            if analytic:
                domain.append(
                    ('analytic_line_ids', 'in', analytic))
            if method is not None and 'cash' in method:
                domain.append(('journal_id', 'in',
                               self.env.company.tax_cash_basis_journal_id.ids))
            initial_move_line_ids = self.env['account.move.line'].search(
                domain)
            initial_total_debit = round(
                sum(initial_move_line_ids.mapped('debit')), 2)
            initial_total_credit = round(
                sum(initial_move_line_ids.mapped('credit')), 2)
            if comparison_number:
                if comparison_type == 'year':
                    for i in range(1, eval(comparison_number) + 1):
                        com_start_date = subtract(start_date, years=i)
                        com_end_date = subtract(end_date, years=i)
                        domain = [('date', '>=', com_start_date),
                                  ('account_id', '=', account_id.id),
                                  ('date', '<=', com_end_date),
                                  ('parent_state', 'in', option_domain), ]
                        if journal_list:
                            domain.append(
                                ('journal_id', 'in', journal_list), )
                        if analytic:
                            domain.append(
                                ('analytic_line_ids', 'in', analytic))
                        if method is not None and 'cash' in method:
                            domain.append(('journal_id', 'in',
                                           self.env.company.tax_cash_basis_journal_id.ids))
                        move_lines = self.env['account.move.line'].search(
                            domain)
                        dynamic_total_debit[
                            f"dynamic_total_debit_{i}"] = round(
                            sum(move_lines.mapped('debit')), 2)
                        dynamic_total_credit[
                            f"dynamic_total_credit_{i}"] = round(
                            sum(move_lines.mapped('credit')), 2)
                if comparison_type == 'month':
                    dynamic_date_num[
                        f"dynamic_date_num{0}"] = self.get_month_name(
                        start_date) + ' ' + str(
                        start_date.year)
                    for i in range(1, eval(comparison_number) + 1):
                        com_start_date = subtract(start_date, months=i)
                        com_end_date = subtract(end_date, months=i)
                        domain = [('date', '>=', com_start_date),
                                  ('account_id', '=', account_id.id),
                                  ('date', '<=', com_end_date),
                                  ('parent_state', 'in', option_domain), ]
                        if journal_list:
                            domain.append(
                                ('journal_id', 'in', journal_list), )
                        if analytic:
                            domain.append(
                                ('analytic_line_ids', 'in', analytic))
                        if method is not None and 'cash' in method:
                            domain.append(('journal_id', 'in',
                                           self.env.company.tax_cash_basis_journal_id.ids), )
                        move_lines = self.env['account.move.line'].search(
                            domain)
                        dynamic_date_num[
                            f"dynamic_date_num{i}"] = self.get_month_name(
                            com_start_date) + ' ' + str(
                            com_start_date.year)
                        dynamic_total_debit[
                            f"dynamic_total_debit_{i}"] = round(
                            sum(move_lines.mapped('debit')), 2)
                        dynamic_total_credit[
                            f"dynamic_total_credit_{i}"] = round(
                            sum(move_lines.mapped('credit')), 2)
                if comparison_type == 'quarter':
                    dynamic_date_num[
                        f"dynamic_date_num{0}"] = 'Q' + ' ' + str(
                        get_quarter_number(start_date)) + ' ' + str(
                        start_date.year)
                    for i in range(1, eval(comparison_number) + 1):
                        com_start_date = subtract(start_date, months=i * 3)
                        com_end_date = subtract(end_date, months=i * 3)
                        domain = [('date', '>=', com_start_date),
                                  ('account_id', '=', account_id.id),
                                  ('date', '<=', com_end_date),
                                  ('parent_state', 'in', option_domain), ]
                        if journal_list:
                            domain.append(
                                ('journal_id', 'in', journal_list), )
                        if analytic:
                            domain.append(
                                ('analytic_line_ids', 'in', analytic))
                        if method is not None and 'cash' in method:
                            domain.append(('journal_id', 'in',
                                           self.env.company.tax_cash_basis_journal_id.ids))
                        move_lines = self.env['account.move.line'].search(
                            domain)
                        dynamic_date_num[
                            f"dynamic_date_num{i}"] = 'Q' + ' ' + str(
                            get_quarter_number(com_start_date)) + ' ' + str(
                            com_start_date.year)
                        dynamic_total_debit[
                            f"dynamic_total_debit_{i}"] = round(
                            sum(move_lines.mapped('debit')), 2)
                        dynamic_total_credit[
                            f"dynamic_total_credit_{i}"] = round(
                            sum(move_lines.mapped('credit')), 2)
            domain = [('date', '>=', start_date),
                      ('account_id', '=', account_id.id),
                      ('date', '<=', end_date),
                      ('parent_state', 'in', option_domain), ]
            if journal_list:
                domain.append(
                    ('journal_id', 'in', journal_list), )
            if analytic:
                domain.append(
                    ('analytic_line_ids', 'in', analytic))
            if method is not None and 'cash' in method:
                domain.append(('journal_id', 'in',
                               self.env.company.tax_cash_basis_journal_id.ids))
            move_line_ids = self.env['account.move.line'].search(domain)
            total_debit = round(sum(move_line_ids.mapped('debit')), 2)
            total_credit = round(sum(move_line_ids.mapped('credit')), 2)
            sum_debit = initial_total_debit + sum(
                dynamic_total_debit.values()) + total_debit
            sum_credit = initial_total_credit + sum(
                dynamic_total_credit.values()) + total_credit
            diff_credit_debit = sum_debit - sum_credit
            if diff_credit_debit > 0:
                end_total_debit = diff_credit_debit
                end_total_credit = 0.0
            else:
                end_total_debit = 0.0
                end_total_credit = abs(diff_credit_debit)
            data = {
                'account': account_id.display_name,
                'account_id': account_id.id,
                'journal_ids': self.env['account.journal'].search_read([], [
                    'name']),
                'initial_total_debit': initial_total_debit,
                'initial_total_credit': initial_total_credit,
                'total_debit': total_debit,
                'total_credit': total_credit,
                'end_total_debit': end_total_debit,
                'end_total_credit': end_total_credit
            }
            if comparison_number:
                if dynamic_date_num:
                    data['dynamic_date_num'] = dynamic_date_num
                for i in range(1, eval(comparison_number) + 1):
                    data[f'dynamic_total_debit_{i}'] = dynamic_total_debit.get(
                        f"dynamic_total_debit_{eval(comparison_number) + 1 - i}",
                        0.0)
                    data[
                        f'dynamic_total_credit_{i}'] = dynamic_total_credit.get(
                        f"dynamic_total_credit_{eval(comparison_number) + 1 - i}",
                        0.0)
            move_line_list.append(data)
        return move_line_list

    @api.model
    def get_xlsx_report(self, data, response, report_name, report_action):
        """
        Generate an XLSX report based on provided data and response stream.
        Generates an Excel workbook with specified report format, including
        subheadings, column headers, and row data for the given financial report
        data, and adds a grand total row at the end.

        :param str data: JSON-encoded data for the report.
        :param response: Response object to stream the generated report.
        :param str report_name: Name of the financial report.
        :param str report_action: Action identifier for the report type.
        """
        data = json.loads(data)
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})

        # Get start and end dates from filters
        start_date = data['filters']['start_date'] if \
            data['filters']['start_date'] else ''
        end_date = data['filters']['end_date'] if \
            data['filters']['end_date'] else ''

        # Define formats for the workbook
        head = workbook.add_format(
            {'font_size': 15, 'align': 'center', 'bold': True})
        sub_heading = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_head = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px',
             'border': 1, 'bg_color': '#D3D3D3',
             'border_color': 'black'})
        filter_body = workbook.add_format(
            {'align': 'center', 'bold': True, 'font_size': '10px'})
        side_heading_sub = workbook.add_format(
            {'align': 'left', 'bold': True, 'font_size': '10px',
             'border': 1,
             'border_color': 'black'})
        side_heading_sub.set_indent(1)
        
        # Format for regular numerical values with IDR currency
        currency_txt_format = workbook.add_format({'font_size': '10px', 'border': 1, 'num_format': '_ "Rp. " #,##0.00'})
        currency_txt_format.set_indent(2)
        
        # Format for grand total row with IDR currency
        grand_total_currency_format = workbook.add_format(
            {'font_size': 10, 'bold': True, 'border': 1, 'bg_color': '#D3D3D3', 'align': 'right', 'num_format': '_ "Rp. " #,##0.00'})


        sheet = workbook.add_worksheet()

        # Set column widths
        sheet.set_column(0, 0, 30)  # Account column
        sheet.set_column(1, 1, 20)  # Initial Debit
        sheet.set_column(2, 2, 20)  # Initial Credit
        # Dynamic columns will be set based on comparison periods

        col = 0
        # Report Title
        sheet.merge_range('A1:B1', report_name, head)

        # Filter Headers
        sheet.write('B3', 'Date Range', filter_head)
        sheet.write('B4', 'Comparison', filter_head)
        sheet.write('B5', 'Journal', filter_head)
        sheet.write('B6', 'Account', filter_head)
        sheet.write('B7', 'Option', filter_head)

        # Filter Values
        if start_date or end_date:
            sheet.merge_range('C3:G3', f"{start_date} to {end_date}",
                              filter_body)
        if data['filters']['comparison_number_range']:
            sheet.merge_range('C4:G4',
                              f"{data['filters']['comparison_type']} : {data['filters']['comparison_number_range']}",
                              filter_body)
        if data['filters']['journal']:
            display_names = [journal for
                             journal in data['filters']['journal']]
            display_names_str = ', '.join(display_names)
            sheet.merge_range('C5:G5', display_names_str, filter_body)
        if data['filters']['account']:
            account_keys = [account.get('display_name', 'undefined') for
                            account in data['filters']['account']]
            account_keys_str = ', '.join(account_keys)
            sheet.merge_range('C6:G6', account_keys_str, filter_body)
        if data['filters']['options']:
            option_keys = list(data['filters']['options'].keys())
            option_keys_str = ', '.join(option_keys)
            sheet.merge_range('C7:G7', option_keys_str, filter_body)

        # Table Headers - Row 9 (Merged Date Views)
        sheet.write(9, col, '', sub_heading) # Empty cell for Account Name
        sheet.merge_range(9, col + 1, 9, col + 2, 'Initial Balance',
                          sub_heading)
        
        # Dynamic Date View Headers
        i = 3
        for date_view in data['date_viewed']:
            sheet.merge_range(9, col + i, 9, col + i + 1, date_view,
                              sub_heading)
            i += 2
        
        # End Balance Header
        sheet.merge_range(9, col + i, 9, col + i + 1, 'End Balance',
                          sub_heading)

        # Table Headers - Row 10 (Debit/Credit)
        sheet.write(10, col, 'Account', sub_heading) # Account column header
        sheet.write(10, col + 1, 'Debit', sub_heading)
        sheet.write(10, col + 2, 'Credit', sub_heading)
        
        # Dynamic Debit/Credit Headers for Date Views
        i = 3
        for date_views in data['date_viewed']:
            sheet.write(10, col + i, 'Debit', sub_heading)
            i += 1
            sheet.write(10, col + i, 'Credit', sub_heading)
            i += 1
        
        # Debit/Credit Headers for End Balance
        sheet.write(10, col + i, 'Debit', sub_heading)
        sheet.write(10, col + (i + 1), 'Credit', sub_heading)

        # Initialize grand totals
        grand_total_initial_debit = 0.0
        grand_total_initial_credit = 0.0
        
        # Dictionary to hold dynamic comparison totals
        grand_total_dynamic_debits = {}
        grand_total_dynamic_credits = {}

        grand_total_debit = 0.0
        grand_total_credit = 0.0
        grand_total_end_debit = 0.0
        grand_total_end_credit = 0.0

        if data:
            if report_action == 'dynamic_accounts_report.action_trial_balance':
                row = 11
                for move_line in data['data'][0]:
                    sheet.write(row, col, move_line['account'],
                                side_heading_sub)
                    
                    # Get values and replace commas before converting to float
                    initial_debit_str = str(move_line.get('initial_total_debit', '0.0')).replace(',', '')
                    initial_credit_str = str(move_line.get('initial_total_credit', '0.0')).replace(',', '')
                    
                    initial_debit = float(initial_debit_str)
                    initial_credit = float(initial_credit_str)

                    sheet.write(row, col + 1, initial_debit, currency_txt_format)
                    sheet.write(row, col + 2, initial_credit, currency_txt_format)

                    # Accumulate initial totals
                    grand_total_initial_debit += initial_debit
                    grand_total_initial_credit += initial_credit

                    j = 3 # Starting column for dynamic data
                    if data['apply_comparison']:
                        number_of_periods = data['comparison_number_range']
                        for num in number_of_periods:
                            dynamic_debit_key = 'dynamic_total_debit_' + str(num)
                            dynamic_credit_key = 'dynamic_total_credit_' + str(num)
                            
                            current_dynamic_debit_str = str(move_line.get(dynamic_debit_key, '0.0')).replace(',', '')
                            current_dynamic_credit_str = str(move_line.get(dynamic_credit_key, '0.0')).replace(',', '')

                            current_dynamic_debit = float(current_dynamic_debit_str)
                            current_dynamic_credit = float(current_dynamic_credit_str)

                            sheet.write(row, col + j, current_dynamic_debit, currency_txt_format)
                            sheet.write(row, col + j + 1, current_dynamic_credit, currency_txt_format)

                            # Accumulate dynamic totals
                            grand_total_dynamic_debits[num] = grand_total_dynamic_debits.get(num, 0.0) + current_dynamic_debit
                            grand_total_dynamic_credits[num] = grand_total_dynamic_credits.get(num, 0.0) + current_dynamic_credit
                            
                            j += 2
                    
                    # Get values and replace commas before converting to float
                    total_debit_str = str(move_line.get('total_debit', '0.0')).replace(',', '')
                    total_credit_str = str(move_line.get('total_credit', '0.0')).replace(',', '')

                    total_debit = float(total_debit_str)
                    total_credit = float(total_credit_str)

                    # Write total debit and credit (for main period)
                    sheet.write(row, col + j, total_debit, currency_txt_format)
                    sheet.write(row, col + j + 1, total_credit, currency_txt_format)

                    # Accumulate total debit and credit
                    grand_total_debit += total_debit
                    grand_total_credit += total_credit

                    # Get values and replace commas before converting to float
                    end_debit_str = str(move_line.get('end_total_debit', '0.0')).replace(',', '')
                    end_credit_str = str(move_line.get('end_total_credit', '0.0')).replace(',', '')

                    end_debit = float(end_debit_str)
                    end_credit = float(end_credit_str)

                    # Write end total debit and credit
                    sheet.write(row, col + j + 2, end_debit, currency_txt_format)
                    sheet.write(row, col + j + 3, end_credit, currency_txt_format)

                    # Accumulate end total debit and credit
                    grand_total_end_debit += end_debit
                    grand_total_end_credit += end_credit

                    row += 1
                
                # Add the Grand Total row
                sheet.write(row, col, 'Grand Total', grand_total_currency_format)
                sheet.write(row, col + 1, grand_total_initial_debit, grand_total_currency_format)
                sheet.write(row, col + 2, grand_total_initial_credit, grand_total_currency_format)

                j = 3 # Starting column for dynamic data in grand total row
                if data['apply_comparison']:
                    number_of_periods = data['comparison_number_range']
                    for num in number_of_periods:
                        sheet.write(row, col + j, grand_total_dynamic_debits.get(num, 0.0), grand_total_currency_format)
                        sheet.write(row, col + j + 1, grand_total_dynamic_credits.get(num, 0.0), grand_total_currency_format)
                        j += 2
                
                sheet.write(row, col + j, grand_total_debit, grand_total_currency_format)
                sheet.write(row, col + j + 1, grand_total_credit, grand_total_currency_format)
                sheet.write(row, col + j + 2, grand_total_end_debit, grand_total_currency_format)
                sheet.write(row, col + j + 3, grand_total_end_credit, grand_total_currency_format)


        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()