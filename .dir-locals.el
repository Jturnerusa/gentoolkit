((python-ts-mode . ((fmt-executable . "black")
                    (fmt-args . ("-"))
                    (eval . (add-hook 'before-save-hook 'fmt-current-buffer nil t)))))
