import { AlertDialog, Button } from '@heroui/react';
import { useTranslation } from 'react-i18next';

interface ConfirmDialogProps {
  isOpen: boolean;
  heading: string;
  body: string;
  confirmLabel: string;
  isPending?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  isOpen,
  heading,
  body,
  confirmLabel,
  isPending,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const { t } = useTranslation();

  return (
    <AlertDialog isOpen={isOpen} onOpenChange={(open) => !open && onCancel()}>
      <AlertDialog.Backdrop>
        <AlertDialog.Container>
          <AlertDialog.Dialog>
            <AlertDialog.Header>
              <AlertDialog.Icon status="danger" />
              <AlertDialog.Heading>{heading}</AlertDialog.Heading>
            </AlertDialog.Header>
            <AlertDialog.Body>
              <p className="text-sm text-muted">{body}</p>
            </AlertDialog.Body>
            <AlertDialog.Footer>
              <Button variant="tertiary" onPress={onCancel}>
                {t('confirm.cancel')}
              </Button>
              <Button variant="danger" isDisabled={isPending} onPress={onConfirm}>
                {confirmLabel}
              </Button>
            </AlertDialog.Footer>
          </AlertDialog.Dialog>
        </AlertDialog.Container>
      </AlertDialog.Backdrop>
    </AlertDialog>
  );
}
