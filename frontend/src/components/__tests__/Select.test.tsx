import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import Select from '../Select';

const DEPARTMENT_PLACEHOLDER = '\u9009\u62e9\u90e8\u95e8';
const EMPTY_DESCRIPTION = '\u6682\u65e0\u6570\u636e';

describe('Select', () => {
  it('shows localized empty state when options are empty', async () => {
    const user = userEvent.setup();
    render(<Select value="" options={[]} onChange={vi.fn()} placeholder={DEPARTMENT_PLACEHOLDER} />);

    await user.click(screen.getByRole('combobox', { name: DEPARTMENT_PLACEHOLDER }));

    expect(await screen.findByText(EMPTY_DESCRIPTION)).toBeInTheDocument();
    expect(screen.queryByText('No data')).not.toBeInTheDocument();
  });
});
