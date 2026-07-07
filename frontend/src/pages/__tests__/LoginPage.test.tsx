import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { ThemeProvider } from '../../theme/theme-provider';
import LoginPage from '../LoginPage';

function renderLogin(initialEntry = '/login') {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/agents" element={<div>智能体页面</div>} />
          <Route path="/models" element={<div>模型页面</div>} />
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe('LoginPage', () => {
  it('提交账号密码后跳转到 redirect 页面', async () => {
    const user = userEvent.setup();
    renderLogin('/login?redirect=/models');

    await user.type(screen.getByLabelText('账号', { exact: true }), 'admin');
    await user.type(screen.getByLabelText('密码', { exact: true }), 'secret');
    await user.click(screen.getByRole('button', { name: '登录' }));

    expect(await screen.findByText('模型页面')).toBeInTheDocument();
  });

  it('账号或密码为空时提示校验错误', async () => {
    const user = userEvent.setup();
    renderLogin();

    await user.click(screen.getByRole('button', { name: '登录' }));

    expect(screen.getByText('请输入账号和密码')).toBeInTheDocument();
  });

  it('可以切换密码可见状态', async () => {
    const user = userEvent.setup();
    renderLogin();

    const password = screen.getByLabelText('密码', { exact: true });
    expect(password).toHaveAttribute('type', 'password');

    await user.click(screen.getByRole('button', { name: '显示密码' }));
    expect(password).toHaveAttribute('type', 'text');

    await user.click(screen.getByRole('button', { name: '隐藏密码' }));
    expect(password).toHaveAttribute('type', 'password');
  });
});
