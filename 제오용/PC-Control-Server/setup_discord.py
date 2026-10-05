import tkinter as tk
from tkinter import messagebox
root=tk.Tk()
root.title('PC Control Server - Discord Token')
root.geometry('540x190')
root.attributes('-topmost',True)
tk.Label(root,text='봇 토큰을 붙여넣고 저장을 누르세요. 채팅에는 보내지 마세요.').pack(pady=15)
entry=tk.Entry(root,show='*',width=65)
entry.pack(padx=15)
def save():
    token=entry.get().strip()
    if len(token)<30:
        messagebox.showerror('확인','봇 토큰을 입력해 주세요.'); return
    import ast
    from pathlib import Path
    path=Path(__file__).resolve().parent/'config.py'
    source=path.read_text(encoding='utf-8')
    lines=source.splitlines(keepends=True)
    settings={'DISCORD_BOT_TOKEN':token,'DISCORD_CHANNEL_ID':'1551901545967394826','REMOTE_PC_CODE':'0001'}
    for node in reversed(ast.parse(source).body):
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in settings for t in node.targets):
            del lines[node.lineno-1:node.end_lineno]
    source=''.join(lines).rstrip()+'\n'+''.join(k+' = '+repr(v)+'\n' for k,v in settings.items())
    ast.parse(source)
    path.write_text(source,encoding='utf-8')
    entry.delete(0,tk.END)
    messagebox.showinfo('완료','config.py에 저장했습니다.')
    root.destroy()
tk.Button(root,text='저장',command=save,width=15).pack(pady=15)
root.after(100,lambda:(root.lift(),entry.focus_force()))
root.mainloop()
